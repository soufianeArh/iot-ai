package com.soufiane.device.service;

import com.soufiane.device.dto.DeviceCreateRequest;
import com.soufiane.device.dto.DeviceResponse;
import com.soufiane.device.dto.DeviceUpdateRequest;
import com.soufiane.device.entity.Device;
import com.soufiane.device.entity.DeviceStatus;
import com.soufiane.device.exception.DeviceNotFoundException;
import com.soufiane.device.exception.DuplicateDeviceCodeException;
import com.soufiane.device.exception.ZoneNotFoundException;
import com.soufiane.device.repository.DeviceRepository;
import com.soufiane.device.repository.DeviceZoneRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

//just bean : part of endpt bcs controller
@Service
@Transactional(readOnly = true)
public class DeviceService {

    private final DeviceRepository deviceRepository;
    private final DeviceZoneRepository zoneRepository;

    public DeviceService(DeviceRepository deviceRepository, DeviceZoneRepository zoneRepository) {
        this.deviceRepository = deviceRepository;
        this.zoneRepository = zoneRepository;
    }

    public List<DeviceResponse> findAll() {
        // One lookup of every zone, then resolve names in memory, rather than
        // a join or a per-row query.
        Map<Long, String> zoneNames = zoneRepository.findAll().stream()
                .collect(Collectors.toMap(z -> z.getId(), z -> z.getName()));
        return deviceRepository.findAll().stream()
                .map(d -> DeviceResponse.from(d, zoneNames.get(d.getZoneId())))
                .toList();
    }

    public DeviceResponse findById(Long id) {
        Device device = getOrThrow(id);
        return DeviceResponse.from(device, zoneName(device.getZoneId()));
    }

    @Transactional
    public DeviceResponse create(DeviceCreateRequest request) {
        if (deviceRepository.existsByDeviceCode(request.deviceCode())) {
            throw new DuplicateDeviceCodeException(request.deviceCode());
        }
        requireZoneExists(request.zoneId());

        DeviceStatus status = request.status() == null ? DeviceStatus.OFFLINE : request.status();
        Device device = new Device(request.name(), request.deviceCode(), request.productKey(), status);
        device.setDescription(request.description());
        device.setLocation(request.location());
        device.setZoneId(request.zoneId());
        Device saved = deviceRepository.save(device);
        return DeviceResponse.from(saved, zoneName(saved.getZoneId()));
    }

    @Transactional
    public DeviceResponse update(Long id, DeviceUpdateRequest request) {
        Device device = getOrThrow(id);
        requireZoneExists(request.zoneId());

        device.setName(request.name());
        device.setProductKey(request.productKey());
        device.setStatus(request.status());
        device.setDescription(request.description());
        device.setLocation(request.location());
        device.setZoneId(request.zoneId());
        // no explicit save(): the entity is managed, JPA flushes on commit
        return DeviceResponse.from(device, zoneName(device.getZoneId()));
    }

    @Transactional
    public void delete(Long id) {
        deviceRepository.delete(getOrThrow(id));
    }

    private void requireZoneExists(Long zoneId) {
        if (zoneId != null && !zoneRepository.existsById(zoneId)) {
            throw new ZoneNotFoundException(zoneId);
        }
    }

    private String zoneName(Long zoneId) {
        if (zoneId == null) return null;
        return zoneRepository.findById(zoneId).map(z -> z.getName()).orElse(null);
    }

    private Device getOrThrow(Long id) {
        return deviceRepository.findById(id)
                .orElseThrow(() -> new DeviceNotFoundException(id));
    }
}
