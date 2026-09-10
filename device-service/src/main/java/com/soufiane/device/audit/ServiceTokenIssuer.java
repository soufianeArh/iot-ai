package com.soufiane.device.audit;

import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import javax.crypto.SecretKey;
import java.time.Instant;
import java.util.Date;

// Mints the short lived SERVICE token this service uses to call auth-service's
// /internal/audit. Same idea as ai-service's service_headers() in Python:
// device-service is calling another backend directly, not on behalf of a
// logged in user, so there is no user token to forward. Signed with the same
// JWT_SECRET (HS512, implied by key length) so auth-service verifies it.
@Component
public class ServiceTokenIssuer {

    private static final long TTL_SECONDS = 300;

    private final SecretKey key;

    public ServiceTokenIssuer(@Value("${jwt.secret}") String secret) {
        this.key = Keys.hmacShaKeyFor(secret.getBytes());
    }

    // Minted fresh per call rather than cached: encoding is cheap and it
    // avoids "cached token expired mid flight" bugs.
    public String token() {
        Instant now = Instant.now();
        return Jwts.builder()
                .subject("device-service")
                .claim("role", "SERVICE")
                .issuedAt(Date.from(now))
                .expiration(Date.from(now.plusSeconds(TTL_SECONDS)))
                .signWith(key)
                .compact();
    }
}
