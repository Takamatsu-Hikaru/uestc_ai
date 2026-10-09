/** True when the typed text allows the delete button to enable. The server re-checks. */
export function matchesConfirmation(expected: string, input: string, caseInsensitive = false): boolean {
  if (!expected) return false;
  if (!caseInsensitive) return input === expected;
  return input.trim().toLowerCase() === expected.trim().toLowerCase();
}
