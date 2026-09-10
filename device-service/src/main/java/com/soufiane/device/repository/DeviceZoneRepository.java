package com.soufiane.device.repository;

import com.soufiane.device.entity.DeviceZone;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface DeviceZoneRepository extends JpaRepository<DeviceZone, Long> {
    Optional<DeviceZone> findByName(String name);
}
