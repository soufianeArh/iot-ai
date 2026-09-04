package com.soufiane.device.repository;

import com.soufiane.device.entity.Device;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;
//free CRUD (findAll, findById, save, delete, existsById...)
public interface DeviceRepository extends JpaRepository<Device, Long> {

    boolean existsByDeviceCode(String deviceCode);

    Optional<Device> findByDeviceCode(String deviceCode);
}
