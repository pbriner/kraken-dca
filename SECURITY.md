# Security Policy

## Security Features

This application has been designed with security as a primary concern and is ready for penetration testing.

### Architecture Security

1. **Minimal Attack Surface**
   - Zero external dependencies (uses only Python standard library)
   - No SQL database (eliminates SQL injection)
   - No shell command execution (eliminates command injection)
   - Direct HTTPS API communication only

2. **Input Validation**
   - All configuration values validated on startup
   - Trading pair format validation
   - Numeric range validation (deposit_day: 1-28)
   - Type checking on all inputs

3. **Secure API Communication**
   - HTTPS only (no HTTP fallback)
   - Proper HMAC-SHA512 signature generation
   - Nonce-based replay attack prevention
   - API keys never logged or exposed in error messages

4. **Container Security**
   - Runs as non-root user (UID 1000)
   - Minimal base image (python:3.11-slim)
   - All capabilities dropped (`cap_drop: ALL`)
   - No privilege escalation (`no-new-privileges:true`)
   - Limited file system access

5. **Data Protection**
   - API credentials stored in config file (should be protected via file permissions)
   - Transaction data in JSON format (no sensitive data exposure)
   - No plaintext password storage
   - No sensitive data in Docker images

### Threat Model

#### Protected Against

✅ **SQL Injection**: No database used
✅ **Command Injection**: No shell execution
✅ **Path Traversal**: Validates and restricts file access
✅ **XSS**: No web interface
✅ **CSRF**: No web interface
✅ **API Key Exposure**: Not logged, not in environment variables
✅ **Privilege Escalation**: Non-root container user
✅ **Replay Attacks**: Nonce-based API signatures
✅ **Man-in-the-Middle**: HTTPS only with certificate verification

#### Risks to Consider

⚠️ **Config File Access**: If attacker gains file system access, API keys are readable
- Mitigation: Use proper file permissions (600), consider encrypted storage
- Recommended: Use Docker secrets or environment variables in production

⚠️ **Docker Host Compromise**: Container isolation protects against application exploits, but not host-level attacks
- Mitigation: Keep Docker host updated, use security scanning

⚠️ **API Key Permissions**: Over-permissioned API keys could allow unauthorized actions
- Mitigation: Use minimal permissions (Query Funds + Create Orders only)
- Never enable: Withdraw Funds permission

⚠️ **Rate Limiting**: Application respects time-based DCA, but doesn't explicitly rate limit API calls
- Mitigation: Kraken enforces server-side rate limits

## Penetration Testing Guidelines

### Recommended Testing Scenarios

1. **Input Validation Testing**
   ```bash
   # Test invalid config values
   - deposit_day: 0, 29, -1, "invalid"
   - crypto_amount: 0, -0.01, "not_a_number"
   - trading_pair: "../../../etc/passwd", "<script>", "'; DROP TABLE--"
   - api_key/api_secret: null, empty string, very long strings
   ```

2. **File System Access Testing**
   ```bash
   # Attempt path traversal
   - Modify config paths to ../../../etc/passwd
   - Attempt to write outside /app directory
   - Test symbolic link following
   ```

3. **API Security Testing**
   ```bash
   # Test API interaction
   - Invalid API credentials
   - Expired/revoked API keys
   - Malformed API requests
   - Replay attack attempts
   ```

4. **Container Escape Testing**
   ```bash
   # Attempt privilege escalation
   docker exec -it kraken-dca /bin/bash
   # Try to access host resources
   # Attempt capability-based exploits
   ```

5. **Denial of Service Testing**
   ```bash
   # Resource exhaustion
   - Very large transaction.json file
   - Rapid API calls (should be prevented by DCA timing)
   - Memory exhaustion attempts
   ```

### Known Limitations

1. **Config File Security**: API credentials stored in plaintext JSON
   - For production, consider using Docker secrets or HashiCorp Vault

2. **No Authentication**: Application assumes trusted environment
   - For multi-user scenarios, add authentication layer

3. **No Rate Limiting**: Relies on Kraken's server-side limits
   - For aggressive strategies, implement client-side rate limiting

4. **Transaction Log Growth**: transactions.json grows indefinitely
   - For long-term use, implement log rotation

### Security Best Practices

1. **File Permissions**
   ```bash
   chmod 600 config.json
   chmod 600 transactions.json
   ```

2. **Docker Secrets** (Production)
   ```yaml
   services:
     kraken-dca:
       secrets:
         - kraken_api_key
         - kraken_api_secret
   
   secrets:
     kraken_api_key:
       external: true
     kraken_api_secret:
       external: true
   ```

3. **Network Isolation**
   ```yaml
   services:
     kraken-dca:
       networks:
         - isolated
   
   networks:
     isolated:
       internal: true  # No internet access except specified
   ```

4. **Regular Updates**
   ```bash
   # Update base image
   docker pull python:3.11-slim
   docker-compose build --no-cache
   ```

## Reporting Vulnerabilities

If you discover a security vulnerability:

1. **Do NOT** open a public GitHub issue
2. Email: [Your Security Email]
3. Provide:
   - Vulnerability description
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

## Security Checklist for Deployment

- [ ] API key has minimal permissions (no withdrawal)
- [ ] config.json has restricted permissions (600)
- [ ] Docker host is updated and patched
- [ ] Container resource limits are set
- [ ] Logs are monitored for suspicious activity
- [ ] Transaction history is backed up regularly
- [ ] API keys are rotated periodically
- [ ] Test with small amounts before production use

## Compliance Notes

- **GDPR**: No personal data collected
- **PCI DSS**: No credit card data handled
- **Financial Regulations**: User responsible for compliance with local laws
- **KYC/AML**: Handled by Kraken exchange

---

Last Updated: February 2025
