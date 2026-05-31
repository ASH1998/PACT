// Package pact implements the client side of the PACT protocol: canonical JSON
// hashing and Ed25519 Action Envelope signing that match the Python backend
// byte-for-byte, plus a thin HTTP client for the gateway.
package pact

import (
	"crypto/ed25519"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"sort"
	"strconv"
	"strings"
)

// CanonicalJSON serializes v exactly like the backend's
//
//	json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
//
// i.e. recursively sorted object keys, no whitespace, UTF-8, and no HTML/unicode
// escaping beyond what Python's json module emits with ensure_ascii=False.
func CanonicalJSON(v any) []byte {
	var b strings.Builder
	writeCanonical(&b, v)
	return []byte(b.String())
}

func writeCanonical(b *strings.Builder, v any) {
	switch t := v.(type) {
	case nil:
		b.WriteString("null")
	case bool:
		if t {
			b.WriteString("true")
		} else {
			b.WriteString("false")
		}
	case string:
		writeCanonicalString(b, t)
	case json.Number:
		b.WriteString(string(t))
	case int:
		b.WriteString(strconv.Itoa(t))
	case int64:
		b.WriteString(strconv.FormatInt(t, 10))
	case float64:
		// Avoid in canonical payloads where possible (int/float ambiguity vs
		// Python). Decode numbers with json.Number to stay faithful.
		b.WriteString(strconv.FormatFloat(t, 'g', -1, 64))
	case map[string]any:
		keys := make([]string, 0, len(t))
		for k := range t {
			keys = append(keys, k)
		}
		sort.Strings(keys) // byte-wise == Python code-point ordering for valid UTF-8
		b.WriteByte('{')
		for i, k := range keys {
			if i > 0 {
				b.WriteByte(',')
			}
			writeCanonicalString(b, k)
			b.WriteByte(':')
			writeCanonical(b, t[k])
		}
		b.WriteByte('}')
	case []any:
		b.WriteByte('[')
		for i, e := range t {
			if i > 0 {
				b.WriteByte(',')
			}
			writeCanonical(b, e)
		}
		b.WriteByte(']')
	default:
		raw, _ := json.Marshal(t)
		b.Write(raw)
	}
}

// writeCanonicalString matches Python json.dumps string escaping with
// ensure_ascii=False: escape only " \ and the C0 control characters (with short
// forms for \b \t \n \f \r); everything else, including non-ASCII, is emitted raw.
func writeCanonicalString(b *strings.Builder, s string) {
	b.WriteByte('"')
	for _, r := range s {
		switch r {
		case '"':
			b.WriteString(`\"`)
		case '\\':
			b.WriteString(`\\`)
		case '\b':
			b.WriteString(`\b`)
		case '\t':
			b.WriteString(`\t`)
		case '\n':
			b.WriteString(`\n`)
		case '\f':
			b.WriteString(`\f`)
		case '\r':
			b.WriteString(`\r`)
		default:
			if r < 0x20 {
				b.WriteString(fmt.Sprintf(`\u%04x`, r))
			} else {
				b.WriteRune(r)
			}
		}
	}
	b.WriteByte('"')
}

// HashPayload returns "sha256:" + hex(sha256(CanonicalJSON(v))), matching the
// backend's hash_payload().
func HashPayload(v any) string {
	sum := sha256.Sum256(CanonicalJSON(v))
	return "sha256:" + hex.EncodeToString(sum[:])
}

// Envelope is a PACT Action Envelope (a plain JSON object).
type Envelope map[string]any

// NewEnvelope builds an unsigned Action Envelope identical in shape to the
// backend's EnvelopeService.create_envelope. parentActionHash may be a string
// or nil (serialized as JSON null).
func NewEnvelope(
	agentID, runID string,
	stepID int,
	tool string,
	args map[string]any,
	intentHash, capabilityTokenHash string,
	provenance map[string]any,
	parentActionHash any,
	timestamp string,
) Envelope {
	if args == nil {
		args = map[string]any{}
	}
	if provenance == nil {
		provenance = map[string]any{}
	}
	return Envelope{
		"protocol":              "PACT/0.1",
		"run_id":                runID,
		"step_id":               stepID,
		"agent_id":              agentID,
		"tool":                  tool,
		"args":                  args,
		"args_digest":           HashPayload(args),
		"intent_hash":           intentHash,
		"capability_token_hash": capabilityTokenHash,
		"provenance":            provenance,
		"parent_action_hash":    parentActionHash,
		"timestamp":             timestamp,
	}
}

// Sign signs the envelope with the agent's base64-encoded Ed25519 private key
// (the 32-byte nacl seed, as returned by /agents/register) and stores the
// base64 signature under "agent_signature". The signature is computed over the
// canonical JSON of the envelope WITHOUT the agent_signature field, exactly as
// the backend verifies it.
func (e Envelope) Sign(privateKeyB64 string) error {
	seed, err := base64.StdEncoding.DecodeString(privateKeyB64)
	if err != nil {
		return fmt.Errorf("decode private key: %w", err)
	}
	if len(seed) != ed25519.SeedSize {
		return fmt.Errorf("private key seed must be %d bytes, got %d", ed25519.SeedSize, len(seed))
	}
	priv := ed25519.NewKeyFromSeed(seed)
	delete(e, "agent_signature")
	payload := CanonicalJSON(map[string]any(e))
	sig := ed25519.Sign(priv, payload)
	e["agent_signature"] = base64.StdEncoding.EncodeToString(sig)
	return nil
}
