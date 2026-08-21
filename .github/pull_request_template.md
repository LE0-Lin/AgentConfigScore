## Summary

<!-- What does this change and why? -->

## Verification

- [ ] `python -m unittest discover -s tests -v`
- [ ] `agent-config-score . --fail-under 90`
- [ ] Added or updated regression tests when behavior changed

## Safety / compatibility

- [ ] No real credentials, tokens, private keys, or private repository content are included
- [ ] Core runtime remains dependency-free, or the new dependency is justified above
- [ ] Detection changes are conservative and explainable
