package com.watchman.repository;

import com.watchman.model.ShiftHandover;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface ShiftHandoverRepository extends JpaRepository<ShiftHandover, Long> {
    Optional<ShiftHandover> findByHandoverCode(String handoverCode);
    List<ShiftHandover> findByStatusOrderByHandoverTimeDesc(String status);
    List<ShiftHandover> findAllByOrderByHandoverTimeDesc();
    List<ShiftHandover> findByIncomingWatchmanIdAndStatus(String incomingWatchmanId, String status);
}
