import os
import subprocess
import sys
from pathlib import Path

def main():
    root = Path(__file__).resolve().parent
    jdk_home = Path(os.environ["LOCALAPPDATA"]) / "jdk-17" / "jdk-17.0.12+7"
    android_sdk = Path(os.environ["LOCALAPPDATA"]) / "Android" / "Sdk"

    env = os.environ.copy()
    env["JAVA_HOME"] = str(jdk_home)
    env["ANDROID_HOME"] = str(android_sdk)
    env["ANDROID_SDK_ROOT"] = str(android_sdk)
    env["PATH"] = f"{jdk_home / 'bin'}{os.pathsep}{env.get('PATH', '')}"

    print("[*] Running RidgeWatch Android Unit Tests...")
    gradlew = root / "gradlew.bat"
    cmd = [str(gradlew), "testDebugUnitTest", "--stacktrace"]

    res = subprocess.run(cmd, cwd=root, env=env)
    sys.exit(res.returncode)

if __name__ == "__main__":
    main()
