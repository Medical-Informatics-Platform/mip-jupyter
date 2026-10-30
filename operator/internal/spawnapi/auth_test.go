package spawnapi

import (
	"context"
	"errors"
	"fmt"
	"time"

	. "github.com/onsi/ginkgo/v2"
	. "github.com/onsi/gomega"

	authenticationv1 "k8s.io/api/authentication/v1"
	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/client-go/kubernetes"
	"k8s.io/utils/ptr"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/client/interceptor"
)

var _ = Describe("TokenReviewAuthenticator", func() {
	var (
		ns      string
		counter int
		auth    *TokenReviewAuthenticator
	)
	token := func(audience string) string {
		clientset, err := kubernetes.NewForConfig(cfg)
		Expect(err).NotTo(HaveOccurred())
		tr, err := clientset.CoreV1().ServiceAccounts(ns).CreateToken(ctx, "jupyterhub", &authenticationv1.TokenRequest{
			Spec: authenticationv1.TokenRequestSpec{Audiences: []string{audience}, ExpirationSeconds: ptr.To[int64](600)},
		}, metav1.CreateOptions{})
		Expect(err).NotTo(HaveOccurred())
		return tr.Status.Token
	}

	BeforeEach(func() {
		counter++
		ns = fmt.Sprintf("federation-auth-%d", counter)
		Expect(k8sClient.Create(ctx, &corev1.Namespace{ObjectMeta: metav1.ObjectMeta{Name: ns}})).To(Succeed())
		Expect(k8sClient.Create(ctx, &corev1.ServiceAccount{ObjectMeta: metav1.ObjectMeta{Name: "jupyterhub", Namespace: ns}})).To(Succeed())
		auth = &TokenReviewAuthenticator{Client: k8sClient}
	})

	It("accepts a token for the mip-notebook-operator audience", func() {
		username, err := auth.Authenticate(ctx, token(Audience))
		Expect(err).NotTo(HaveOccurred())
		Expect(username).To(Equal("system:serviceaccount:" + ns + ":jupyterhub"))
	})
	It("rejects a token for another audience", func() {
		_, err := auth.Authenticate(ctx, token("https://kubernetes.default.svc"))
		Expect(err).To(MatchError(ErrUnauthenticated))
	})
	It("rejects a token that is not one", func() {
		_, err := auth.Authenticate(ctx, "not-a-token")
		Expect(err).To(MatchError(ErrUnauthenticated))
	})
	It("rejects an answer that does not confirm the audience", func() {
		auth.Client = interceptor.NewClient(k8sClient, interceptor.Funcs{
			Create: func(_ context.Context, _ client.WithWatch, obj client.Object, _ ...client.CreateOption) error {
				tr := obj.(*authenticationv1.TokenReview)
				tr.Status = authenticationv1.TokenReviewStatus{
					Authenticated: true,
					User:          authenticationv1.UserInfo{Username: "system:serviceaccount:" + ns + ":jupyterhub"},
					Audiences:     []string{"https://kubernetes.default.svc"},
				}
				return nil
			},
		})
		_, err := auth.Authenticate(ctx, "anything")
		Expect(err).To(MatchError(ErrUnauthenticated))
	})
})

type countingAuth struct {
	calls int
	err   error
}

func (c *countingAuth) Authenticate(_ context.Context, token string) (string, error) {
	c.calls++
	if c.err != nil {
		return "", c.err
	}
	return "user-" + token, nil
}

var _ = Describe("CachedAuthenticator", func() {
	var (
		next  *countingAuth
		cache *CachedAuthenticator
		now   time.Time
	)
	BeforeEach(func() {
		next = &countingAuth{}
		cache = NewCachedAuthenticator(next, time.Minute, 2)
		now = time.Unix(1_000_000, 0)
		cache.now = func() time.Time { return now }
	})

	It("remembers a valid token for the TTL only", func() {
		for range 3 {
			Expect(cache.Authenticate(ctx, "a")).To(Equal("user-a"))
		}
		Expect(next.calls).To(Equal(1))
		now = now.Add(time.Minute)
		Expect(cache.Authenticate(ctx, "a")).To(Equal("user-a"))
		Expect(next.calls).To(Equal(2))
	})
	It("does not remember failures", func() {
		next.err = ErrUnauthenticated
		for range 2 {
			_, err := cache.Authenticate(ctx, "a")
			Expect(err).To(MatchError(ErrUnauthenticated))
		}
		next.err = errors.New("timeout")
		_, err := cache.Authenticate(ctx, "a")
		Expect(err).To(HaveOccurred())
		Expect(next.calls).To(Equal(3))
	})
	It("is bounded, and evicts expired entries first", func() {
		Expect(cache.Authenticate(ctx, "a")).To(Equal("user-a"))
		Expect(cache.Authenticate(ctx, "b")).To(Equal("user-b"))
		Expect(cache.Authenticate(ctx, "c")).To(Equal("user-c"))
		Expect(cache.entries).To(HaveLen(2))
		Expect(cache.Authenticate(ctx, "c")).To(Equal("user-c"))
		Expect(next.calls).To(Equal(4), "c was not cached while full")

		now = now.Add(time.Minute)
		Expect(cache.Authenticate(ctx, "c")).To(Equal("user-c"))
		Expect(cache.entries).To(HaveLen(1))
	})
	It("keys entries by hash, not by token", func() {
		Expect(cache.Authenticate(ctx, "secret-token")).To(Equal("user-secret-token"))
		for k := range cache.entries {
			Expect(string(k[:])).NotTo(ContainSubstring("secret-token"))
		}
	})
})
