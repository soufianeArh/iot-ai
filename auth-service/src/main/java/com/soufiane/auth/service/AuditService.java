package com.soufiane.auth.service;

import com.soufiane.auth.dto.AuditReport;
import com.soufiane.auth.dto.AuditRow;
import com.soufiane.auth.entity.AuditLog;
import com.soufiane.auth.repository.AuditLogRepository;
import jakarta.persistence.criteria.Predicate;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;

@Service
@Transactional(readOnly = true)
public class AuditService {

    private final AuditLogRepository repository;

    public AuditService(AuditLogRepository repository) {
        this.repository = repository;
    }

    @Transactional
    public void record(AuditReport r) {
        repository.save(new AuditLog(r.actor(), r.actorRole(), r.service(), r.method(), r.action(),
                r.resource(), r.resourceId(), r.path(), r.status(), r.outcome(), r.ip()));
    }

    // Convenience for the events auth-service records about itself (login,
    // logout), where there is no HTTP round trip and no security context.
    @Transactional
    public void record(String actor, String actorRole, String action, String resource,
                       String resourceId, String path, int status, String outcome, String ip) {
        repository.save(new AuditLog(actor, actorRole, "auth-service", methodFor(action), action,
                resource, resourceId, path, status, outcome, ip));
    }

    private static String methodFor(String action) {
        return switch (action) {
            case "UPDATE" -> "PUT";
            case "DELETE" -> "DELETE";
            default -> "POST";
        };
    }

    public List<AuditRow> search(String actor, String action, String resource,
                                 OffsetDateTime from, OffsetDateTime to, int limit) {
        Specification<AuditLog> spec = (root, query, cb) -> {
            List<Predicate> predicates = new ArrayList<>();
            if (notBlank(actor)) predicates.add(cb.equal(root.get("actor"), actor));
            if (notBlank(action)) predicates.add(cb.equal(root.get("action"), action));
            if (notBlank(resource)) predicates.add(cb.equal(root.get("resource"), resource));
            if (from != null) predicates.add(cb.greaterThanOrEqualTo(root.<OffsetDateTime>get("at"), from));
            if (to != null) predicates.add(cb.lessThanOrEqualTo(root.<OffsetDateTime>get("at"), to));
            return cb.and(predicates.toArray(new Predicate[0]));
        };
        PageRequest page = PageRequest.of(0, Math.min(Math.max(limit, 1), 500),
                Sort.by(Sort.Direction.DESC, "at"));
        return repository.findAll(spec, page).map(AuditRow::from).getContent();
    }

    private static boolean notBlank(String s) {
        return s != null && !s.isBlank();
    }
}
