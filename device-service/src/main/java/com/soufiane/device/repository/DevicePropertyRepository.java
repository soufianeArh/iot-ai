package com.soufiane.device.repository;

import com.soufiane.device.entity.DeviceProperty;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;

public interface DevicePropertyRepository extends JpaRepository<DeviceProperty, Long> {


     // Latest reading for each distinct key of one device.
     // DISTINCT ON is Postgres-specific: it keeps the first row of each group,
     //which the ORDER BY makes the most recent one.

    @Query(value = """
            SELECT DISTINCT ON (property_key) *
            FROM device_property
            WHERE device_id = :deviceId
            ORDER BY property_key, recorded_at DESC
            """, nativeQuery = true)
    List<DeviceProperty> findLatestPerKey(@Param("deviceId") Long deviceId);

    List<DeviceProperty> findByDeviceIdAndPropertyKeyOrderByRecordedAtDesc(Long deviceId,
                                                                          String propertyKey,
                                                                          Pageable pageable);
}
