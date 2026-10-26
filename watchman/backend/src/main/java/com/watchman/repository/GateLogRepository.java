package com.watchman.repository;

import com.watchman.model.GateLog;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;
import java.util.List;

@Repository
public interface GateLogRepository extends JpaRepository<GateLog, Long> {
    List<GateLog> findTop50ByOrderByEntryTimeDesc();
    List<GateLog> findByIdentifierOrderByEntryTimeDesc(String identifier);
    long countByDirectionAndExitTimeIsNull(String direction);
}
