// Command parity is a test helper: it reads an envelope spec as JSON on stdin,
// builds + signs the Action Envelope with the pact package, and prints the
// canonical bytes (base64), the args/envelope hashes, and the signed envelope.
// A Python harness then verifies the signature with the real backend code.
package main

import (
	"encoding/base64"
	"encoding/json"
	"fmt"
	"os"

	"pacttui/internal/pact"
)

type spec struct {
	PrivateKeyB64       string         `json:"private_key_b64"`
	AgentID             string         `json:"agent_id"`
	RunID               string         `json:"run_id"`
	StepID              int            `json:"step_id"`
	Tool                string         `json:"tool"`
	Args                map[string]any `json:"args"`
	IntentHash          string         `json:"intent_hash"`
	CapabilityTokenHash string         `json:"capability_token_hash"`
	Provenance          map[string]any `json:"provenance"`
	ParentActionHash    any            `json:"parent_action_hash"`
	Timestamp           string         `json:"timestamp"`
}

func main() {
	dec := json.NewDecoder(os.Stdin)
	dec.UseNumber() // keep numbers faithful (int vs float)
	var s spec
	if err := dec.Decode(&s); err != nil {
		fmt.Fprintln(os.Stderr, "decode spec:", err)
		os.Exit(1)
	}

	env := pact.NewEnvelope(
		s.AgentID, s.RunID, s.StepID, s.Tool, s.Args,
		s.IntentHash, s.CapabilityTokenHash, s.Provenance,
		s.ParentActionHash, s.Timestamp,
	)

	// Canonical bytes of the unsigned envelope (what gets signed).
	canonicalUnsigned := pact.CanonicalJSON(map[string]any(env))
	envHashUnsigned := pact.HashPayload(map[string]any(env))
	argsDigest := pact.HashPayload(s.Args)

	if err := env.Sign(s.PrivateKeyB64); err != nil {
		fmt.Fprintln(os.Stderr, "sign:", err)
		os.Exit(1)
	}

	out := map[string]any{
		"canonical_unsigned_b64": base64.StdEncoding.EncodeToString(canonicalUnsigned),
		"envelope_hash_unsigned": envHashUnsigned,
		"args_digest":            argsDigest,
		"signed_envelope":        map[string]any(env),
	}
	enc := json.NewEncoder(os.Stdout)
	if err := enc.Encode(out); err != nil {
		fmt.Fprintln(os.Stderr, "encode:", err)
		os.Exit(1)
	}
}
