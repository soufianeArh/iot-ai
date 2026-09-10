-- V3 created audit_log.status as SMALLINT, but the JPA entity maps it as an
-- int, which Hibernate's schema validation expects to be INTEGER. Widen the
-- column so validation passes. An HTTP status fits either type.
ALTER TABLE audit_log ALTER COLUMN status TYPE INTEGER;
