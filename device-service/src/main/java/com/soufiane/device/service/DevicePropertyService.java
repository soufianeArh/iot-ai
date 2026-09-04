package com.soufiane.device.service;

import com.soufiane.device.dto.DevicePropertyResponse;
import com.soufiane.device.exception.DeviceNotFoundException;
import com.soufiane.device.repository.DevicePropertyRepository;
import com.soufiane.device.repository.DeviceRepository;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
@Transactional(readOnly = true)
public class DevicePropertyService {

    private final DeviceRepository deviceRepository;
    private final DevicePropertyRepository devicePropertyRepository;

    public DevicePropertyService(DeviceRepository deviceRepository,
                                 DevicePropertyRepository devicePropertyRepository) {
        this.deviceRepository = deviceRepository;
        this.devicePropertyRepository = devicePropertyRepository;
    }

//gets the current value
    public List<DevicePropertyResponse> latest(Long deviceId) {
        requireDevice(deviceId);
        return devicePropertyRepository.findLatestPerKey(deviceId).stream()
                .map(DevicePropertyResponse::from)
                .toList();
    }

    public List<DevicePropertyResponse> history(Long deviceId, String key, int limit) {
        requireDevice(deviceId);
        //the history is limited
        return devicePropertyRepository
                .findByDeviceIdAndPropertyKeyOrderByRecordedAtDesc(deviceId, key, PageRequest.of(0, limit))
                .stream()
                .map(DevicePropertyResponse::from)
                .toList();
    }
    //check if decide still exist before fetch data
    private void requireDevice(Long deviceId) {
        if (!deviceRepository.existsById(deviceId)) {
            throw new DeviceNotFoundException(deviceId);
        }
    }
}
