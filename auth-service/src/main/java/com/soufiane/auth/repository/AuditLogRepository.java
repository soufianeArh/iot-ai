package com.soufiane.auth.repository;

import com.soufiane.auth.entity.AuditLog;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;

// Specifications rather than one big "(:x is null or col = :x)" JPQL string:
// Postgres cannot infer the type of a bound parameter that only ever appears
// next to IS NULL, and the Criteria API just omits the clause instead.
public interface AuditLogRepository extends JpaRepository<AuditLog, Long>,
        JpaSpecificationExecutor<AuditLog> {
}
