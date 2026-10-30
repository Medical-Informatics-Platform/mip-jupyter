package spawnapi

import (
	"context"
	"crypto/sha256"
	"errors"
	"fmt"
	"slices"
	"sync"
	"time"

	authenticationv1 "k8s.io/api/authentication/v1"
	"sigs.k8s.io/controller-runtime/pkg/client"
)

// Audience of the hub's projected token. The API server does not accept it, so
// the token is useless anywhere but here.
const Audience = "mip-notebook-operator"

// ErrUnauthenticated means the token is not valid for Audience.
var ErrUnauthenticated = errors.New("token is not valid for audience " + Audience)

// Authenticator maps a bearer token to a Kubernetes user name.
type Authenticator interface {
	// Authenticate returns ErrUnauthenticated for a token that is not valid,
	// another error when it cannot tell.
	Authenticate(ctx context.Context, token string) (string, error)
}

// TokenReviewAuthenticator asks the API server (tokenreviews create).
type TokenReviewAuthenticator struct {
	Client client.Client
}

func (a *TokenReviewAuthenticator) Authenticate(ctx context.Context, token string) (string, error) {
	tr := &authenticationv1.TokenReview{Spec: authenticationv1.TokenReviewSpec{
		Token:     token,
		Audiences: []string{Audience},
	}}
	if err := a.Client.Create(ctx, tr); err != nil {
		return "", fmt.Errorf("token review: %w", err)
	}
	// An authenticator without audience support may ignore spec.audiences;
	// status.audiences is what was actually checked.
	if !tr.Status.Authenticated || !slices.Contains(tr.Status.Audiences, Audience) {
		return "", ErrUnauthenticated
	}
	return tr.Status.User.Username, nil
}

// CachedAuthenticator remembers positive answers for TTL. A pod-bound token is
// revoked with its pod, so TTL stays short whatever the token's own lifetime.
type CachedAuthenticator struct {
	Next    Authenticator
	TTL     time.Duration
	MaxSize int
	now     func() time.Time

	mu      sync.Mutex
	entries map[[sha256.Size]byte]cacheEntry
}

type cacheEntry struct {
	username string
	expires  time.Time
}

func NewCachedAuthenticator(next Authenticator, ttl time.Duration, maxSize int) *CachedAuthenticator {
	return &CachedAuthenticator{Next: next, TTL: ttl, MaxSize: maxSize, now: time.Now,
		entries: map[[sha256.Size]byte]cacheEntry{}}
}

func (c *CachedAuthenticator) Authenticate(ctx context.Context, token string) (string, error) {
	key := sha256.Sum256([]byte(token))
	now := c.now()
	c.mu.Lock()
	e, ok := c.entries[key]
	c.mu.Unlock()
	if ok && now.Before(e.expires) {
		return e.username, nil
	}

	username, err := c.Next.Authenticate(ctx, token)
	if err != nil {
		return "", err
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	if len(c.entries) >= c.MaxSize {
		for k, e := range c.entries {
			if !now.Before(e.expires) {
				delete(c.entries, k)
			}
		}
	}
	// Still full: skip caching rather than evict live entries under a flood.
	if len(c.entries) < c.MaxSize {
		c.entries[key] = cacheEntry{username: username, expires: now.Add(c.TTL)}
	}
	return username, nil
}
