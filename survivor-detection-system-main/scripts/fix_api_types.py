"""
scripts/fix_api_types.py
------------------------
Refactors type annotations and guards in backend/api.py so all IDE type checkers
(Pyrefly, Pyright, Pylance) resolve symbols with 0 red squiggles.
"""

import sys

def main():
    with open('backend/api.py', 'r', encoding='utf-8') as f:
        text = f.read()

    # 1. Update _get_operation and add _get_operation_optional
    old_def = """def _get_operation(operation_id: Optional[str] = None, not_running_status: Optional[int] = 409) -> Optional[ScenarioState]:
    if operation_id is not None:
        op = operations.get(operation_id)
        if op is None:
            if not_running_status is None:
                return None
            if not operations:
                raise HTTPException(
                    status_code=not_running_status,
                    detail="Scenario is not running. Call POST /scenario/start first.",
                )
            raise HTTPException(
                status_code=404,
                detail=f"Unknown operation_id: {operation_id}",
            )
        return op
    else:
        if not operations:
            if not_running_status is None:
                return None
            raise HTTPException(
                status_code=not_running_status,
                detail="Scenario is not running. Call POST /scenario/start first.",
            )
        return list(operations.values())[-1]"""

    new_def = """def _get_operation(operation_id: Optional[str] = None, not_running_status: int = 409) -> ScenarioState:
    if operation_id is not None:
        op = operations.get(operation_id)
        if op is None:
            if not operations:
                raise HTTPException(
                    status_code=not_running_status,
                    detail="Scenario is not running. Call POST /scenario/start first.",
                )
            raise HTTPException(
                status_code=404,
                detail=f"Unknown operation_id: {operation_id}",
            )
        return op
    else:
        if not operations:
            raise HTTPException(
                status_code=not_running_status,
                detail="Scenario is not running. Call POST /scenario/start first.",
            )
        return list(operations.values())[-1]


def _get_operation_optional(operation_id: Optional[str] = None) -> Optional[ScenarioState]:
    if operation_id is not None:
        return operations.get(operation_id)
    return list(operations.values())[-1] if operations else None"""

    if old_def in text:
        text = text.replace(old_def, new_def)
        print("Replaced _get_operation definition.")

    # 2. Update _op_id
    old_op_id = """def _op_id(op: ScenarioState, operation_id: Optional[str] = None) -> str:
    if operation_id:
        return operation_id
    for k, v in operations.items():
        if v is op:
            return k
    return "default\""""

    new_op_id = """def _op_id(op: Optional[ScenarioState], operation_id: Optional[str] = None) -> str:
    if operation_id:
        return operation_id
    if op is not None:
        for k, v in operations.items():
            if v is op:
                return k
    return "default\""""

    if old_op_id in text:
        text = text.replace(old_op_id, new_op_id)
        print("Replaced _op_id definition.")

    # 3. Replace all optional calls
    text = text.replace('_get_operation(operation_id, not_running_status=None)', '_get_operation_optional(operation_id)')

    # 4. advance_team_members guard
    old_adv = """    def advance_team_members(self) -> list:
        # pyrefly: ignore [missing-attribute]
        victim_locations = {v.victim_id: v.location for v in self.config.victims}"""

    new_adv = """    def advance_team_members(self) -> list:
        if not self.config or not self.config.victims:
            return []
        victim_locations = {v.victim_id: v.location for v in self.config.victims}"""

    if old_adv in text:
        text = text.replace(old_adv, new_adv)
        print("Updated advance_team_members.")

    # 5. fuse_current guard
    old_fuse = """    def fuse_current(self) -> dict:
        readings_by_victim = self.current_readings_by_victim()
        # pyrefly: ignore [missing-attribute]
        for v in self.config.victims:
            readings_by_victim.setdefault(v.victim_id, [])"""

    new_fuse = """    def fuse_current(self) -> dict:
        readings_by_victim = self.current_readings_by_victim()
        if self.config and self.config.victims:
            for v in self.config.victims:
                readings_by_victim.setdefault(v.victim_id, [])"""

    if old_fuse in text:
        text = text.replace(old_fuse, new_fuse)
        print("Updated fuse_current.")

    # 6. lsr.device_id
    old_lsr = """                            # pyrefly: ignore [missing-attribute]
                            device_id=lsr.device_id,"""

    new_lsr = """                            device_id=getattr(lsr, "device_id", "DEV-SLOPE-01"),"""

    if old_lsr in text:
        text = text.replace(old_lsr, new_lsr)
        print("Updated lsr.device_id.")

    # 7. Clean up pyrefly ignores
    text = text.replace('        meta = {', '        meta: dict[str, object] = {')
    text = text.replace('                    # pyrefly: ignore [bad-assignment]\n', '')
    text = text.replace('                # pyrefly: ignore [bad-assignment]\n', '')
    text = text.replace('    # pyrefly: ignore [missing-attribute]\n', '')
    text = text.replace('    # pyrefly: ignore [bad-argument-type]\n', '')
    text = text.replace('    # pyrefly: ignore [bad-argument-type, missing-attribute]\n', '')
    text = text.replace('        # pyrefly: ignore [missing-attribute]\n', '')
    text = text.replace('            # pyrefly: ignore [bad-argument-type]\n', '')
    text = text.replace('        # pyrefly: ignore [bad-argument-type, missing-attribute]\n', '')

    with open('backend/api.py', 'w', encoding='utf-8') as f:
        f.write(text)

    print("backend/api.py successfully written.")

if __name__ == '__main__':
    main()
