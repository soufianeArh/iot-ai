package com.soufiane.auth.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.time.OffsetDateTime;

// table creation is entirely Flyway's job (V3__audit_log.sql). One row per
// mutating request, from any service in the stack.
@Entity
@Table(name = "audit_log")
public class AuditLog {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "at", nullable = false, insertable = false, updatable = false)
    private OffsetDateTime at;

    @Column(name = "actor", length = 64)
    private String actor;

    @Column(name = "actor_role", length = 16)
    private String actorRole;

    @Column(name = "service", nullable = false, length = 32)
    private String service;

    @Column(name = "method", nullable = false, length = 8)
    private String method;

    @Column(name = "action", nullable = false, length = 16)
    private String action;

    @Column(name = "resource", length = 32)
    private String resource;

    @Column(name = "resource_id", length = 64)
    private String resourceId;

    @Column(name = "path", nullable = false, length = 255)
    private String path;

    @Column(name = "status", nullable = false)
    private int status;

    @Column(name = "outcome", nullable = false, length = 16)
    private String outcome;

    @Column(name = "ip", length = 45)
    private String ip;

    protected AuditLog() {
        // required by JPA
    }

    public AuditLog(String actor, String actorRole, String service, String method, String action,
                    String resource, String resourceId, String path, int status, String outcome, String ip) {
        this.actor = actor;
        this.actorRole = actorRole;
        this.service = service;
        this.method = method;
        this.action = action;
        this.resource = resource;
        this.resourceId = resourceId;
        this.path = path;
        this.status = status;
        this.outcome = outcome;
        this.ip = ip;
    }

    public Long getId() {
        return id;
    }

    public OffsetDateTime getAt() {
        return at;
    }

    public String getActor() {
        return actor;
    }

    public String getActorRole() {
        return actorRole;
    }

    public String getService() {
        return service;
    }

    public String getMethod() {
        return method;
    }

    public String getAction() {
        return action;
    }

    public String getResource() {
        return resource;
    }

    public String getResourceId() {
        return resourceId;
    }

    public String getPath() {
        return path;
    }

    public int getStatus() {
        return status;
    }

    public String getOutcome() {
        return outcome;
    }

    public String getIp() {
        return ip;
    }
}
