package com.soufiane.device.audit;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

// Ships one audit row to auth-service, off the request thread and best
// effort: a logging hiccup must never turn into a failed device write. If
// AUTH_SERVICE_URL is unset (e.g. a local run without the full stack) this
// quietly does nothing.
@Component
public class AuditReporter {

    private static final Logger log = LoggerFactory.getLogger(AuditReporter.class);

    private final ServiceTokenIssuer tokens;
    private final RestClient client;
    private final boolean enabled;

    public AuditReporter(@Value("${audit.auth-service-url:}") String authServiceUrl,
                          ServiceTokenIssuer tokens) {
        this.tokens = tokens;
        this.enabled = authServiceUrl != null && !authServiceUrl.isBlank();
        this.client = RestClient.builder()
                .baseUrl(this.enabled ? authServiceUrl : "http://audit-disabled.invalid")
                .build();
        if (!this.enabled) {
            log.warn("audit reporting disabled: audit.auth-service-url (AUTH_SERVICE_URL) is not set");
        }
    }

    @Async
    public void send(AuditReport report) {
        if (!enabled) return;
        try {
            client.post().uri("/internal/audit")
                    .header("Authorization", "Bearer " + tokens.token())
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(report)
                    .retrieve()
                    .toBodilessEntity();
        } catch (Exception e) {
            log.debug("audit row dropped ({} {}): {}", report.method(), report.path(), e.toString());
        }
    }
}
