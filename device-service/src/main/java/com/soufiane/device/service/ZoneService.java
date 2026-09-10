package com.soufiane.device.service;

import com.soufiane.device.dto.ZoneRequest;
import com.soufiane.device.dto.ZoneResponse;
import com.soufiane.device.entity.DeviceZone;
import com.soufiane.device.exception.DuplicateZoneNameException;
import com.soufiane.device.exception.ZoneNotFoundException;
import com.soufiane.device.repository.DeviceRepository;
import com.soufiane.device.repository.DeviceZoneRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
@Transactional(readOnly = true)
public class ZoneService {

    private final DeviceZoneRepository zoneRepository;
    private final DeviceRepository deviceRepository;

    public ZoneService(DeviceZoneRepository zoneRepository, DeviceRepository deviceRepository) {
        this.zoneRepository = zoneRepository;
        this.deviceRepository = deviceRepository;
    }

    public List<ZoneResponse> findAll() {
        return zoneRepository.findAll().stream()
                .map(z -> ZoneResponse.from(z, deviceRepository.countByZoneId(z.getId())))
                .toList();
    }

    @Transactional
    public ZoneResponse create(ZoneRequest request) {
        zoneRepository.findByName(request.name()).ifPresent(z -> {
            throw new DuplicateZoneNameException(request.name());
        });
        DeviceZone zone = new DeviceZone(request.name(), request.description());
        DeviceZone saved = zoneRepository.save(zone);
        return ZoneResponse.from(saved, 0);
    }

    @Transactional
    public ZoneResponse update(Long id, ZoneRequest request) {
        DeviceZone zone = getOrThrow(id);
        if (!zone.getName().equals(request.name())) {
            zoneRepository.findByName(request.name()).ifPresent(other -> {
                throw new DuplicateZoneNameException(request.name());
            });
            zone.setName(request.name());
        }
        zone.setDescription(request.description());
        return ZoneResponse.from(zone, deviceRepository.countByZoneId(id));
    }

    @Transactional
    public void delete(Long id) {
        // The zone_id FK is ON DELETE SET NULL, so devices in this zone keep
        // existing, just unassigned.
        zoneRepository.delete(getOrThrow(id));
    }

    private DeviceZone getOrThrow(Long id) {
        return zoneRepository.findById(id).orElseThrow(() -> new ZoneNotFoundException(id));
    }
}
