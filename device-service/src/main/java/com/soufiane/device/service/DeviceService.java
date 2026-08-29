package com.soufiane.device.service;

import com.soufiane.device.dto.DeviceCreateRequest;
import com.soufiane.device.dto.DeviceResponse;
import com.soufiane.device.dto.DeviceUpdateRequest;
import com.soufiane.device.entity.Device;
import com.soufiane.device.entity.DeviceStatus;
import com.soufiane.device.exception.DeviceNotFoundException;
import com.soufiane.device.exception.DuplicateDeviceCodeException;
import com.soufiane.device.repository.DeviceRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
@Transactional(readOnly = true)
public class DeviceService {

    private final DeviceRepository deviceRepository;

    public DeviceService(DeviceRepository deviceRepository) {
        this.deviceRepository = deviceRepository;
    }

    public List<DeviceResponse> findAll() {
        return deviceRepository.findAll().stream()
                .map(DeviceResponse::from)
                .toList();
    }

    public DeviceResponse findById(Long id) {
        return DeviceResponse.from(getOrThrow(id));
    }

    @Transactional
    public DeviceResponse create(DeviceCreateRequest request) {
        if (deviceRepository.existsByDeviceCode(request.deviceCode())) {
            throw new DuplicateDeviceCodeException(request.deviceCode());
        }
        DeviceStatus status = request.status() == null ? DeviceStatus.OFFLINE : request.status();
        Device device = new Device(request.name(), request.deviceCode(), request.productKey(), status);
        return DeviceResponse.from(deviceRepository.save(device));
    }

    @Transactional
    public DeviceResponse update(Long id, DeviceUpdateRequest request) {
        Device device = getOrThrow(id);
        device.setName(request.name());
        device.setProductKey(request.productKey());
        device.setStatus(request.status());
        // no explicit save(): the entity is managed, JPA flushes on commit
        return DeviceResponse.from(device);
    }

    @Transactional
    public void delete(Long id) {
        deviceRepository.delete(getOrThrow(id));
    }

    private Device getOrThrow(Long id) {
        return deviceRepository.findById(id)
                .orElseThrow(() -> new DeviceNotFoundException(id));
    }
}
