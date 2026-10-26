package com.watchman.repository;

import com.watchman.model.HandoverTask;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface HandoverTaskRepository extends JpaRepository<HandoverTask, Long> {
    Optional<HandoverTask> findByTaskCode(String taskCode);
    List<HandoverTask> findByHandoverCode(String handoverCode);
    List<HandoverTask> findByStatusNotOrderByCreatedAtDesc(String status);
    List<HandoverTask> findAllByOrderByCreatedAtDesc();
}
