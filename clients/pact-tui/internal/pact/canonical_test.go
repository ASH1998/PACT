package pact

import "testing"

func TestCanonicalJSON(t *testing.T) {
	cases := []struct {
		name string
		in   any
		want string
	}{
		{"sorted keys + int", map[string]any{"b": 1, "a": "x"}, `{"a":"x","b":1}`},
		{"escaping", map[string]any{"s": "a\nb\"c\\d"}, `{"s":"a\nb\"c\\d"}`},
		{"nested sorted", map[string]any{"z": 1, "a": []any{3, 2, "x"}}, `{"a":[3,2,"x"],"z":1}`},
		{"unicode + html chars raw", map[string]any{"k": "café ☕ <t> & \"q\""}, `{"k":"café ☕ <t> & \"q\""}`},
		{"empty object/null", map[string]any{"o": map[string]any{}, "n": nil}, `{"n":null,"o":{}}`},
	}
	for _, c := range cases {
		if got := string(CanonicalJSON(c.in)); got != c.want {
			t.Errorf("%s: got %q want %q", c.name, got, c.want)
		}
	}
}

// TestArgsDigestParity pins the args digest to the value the Python backend's
// hash_payload() produced for identical args (see the crypto parity check).
// This guards canonical-JSON parity without needing the backend.
func TestArgsDigestParity(t *testing.T) {
	args := map[string]any{
		"to":      "bob@acme.com",
		"subject": "café ☕ 日本語 <tag> & \"quoted\" / slash",
		"body":    "line1\nline2\ttabbed\rreturn",
		"nested":  map[string]any{"z": 1, "a": []any{3, 2, "x"}, "ratio": 1.5},
		"count":   5,
	}
	const want = "sha256:9f520b37dfed6e8884c3c6f95b28678aa3c39b676b6bc7b171828a907b1d2831"
	if got := HashPayload(args); got != want {
		t.Errorf("args digest parity broken:\n got %s\n want %s", got, want)
	}
}

func TestSignProducesSignature(t *testing.T) {
	// seed = bytes(range(32)) base64, matching the parity harness key.
	const privB64 = "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8="
	env := NewEnvelope("a", "run_x", 0, "web.read",
		map[string]any{"url": "https://example.com"}, "sha256:ab", "sha256:cd",
		map[string]any{}, nil, "2026-05-30T00:00:00+00:00")
	if err := env.Sign(privB64); err != nil {
		t.Fatalf("sign: %v", err)
	}
	if sig, _ := env["agent_signature"].(string); len(sig) < 80 {
		t.Errorf("expected a base64 ed25519 signature, got %q", sig)
	}
}
