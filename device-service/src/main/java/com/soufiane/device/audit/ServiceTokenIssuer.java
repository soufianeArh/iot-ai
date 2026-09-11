package com.soufiane.device.audit;

import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import javax.crypto.SecretKey;
import java.time.Instant;
import java.util.Date;

// Mints the short lived SERVICE token used to call auth-service's
// /internal/audit, same idea as ai-service's service_headers() in Python:
// there's no user token to forward for a call the service makes on its own.
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
