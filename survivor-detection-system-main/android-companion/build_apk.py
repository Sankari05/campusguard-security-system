import os
import subprocess
import sys
from pathlib import Path

def main():
    root = Path(__file__).resolve().parent
    candidates = [
        Path("C:/Program Files/Microsoft/jdk-17.0.20.101-hotspot"),
        Path(os.environ["LOCALAPPDATA"]) / "jdk-17" / "jdk-17.0.12+7",
        Path("C:/Program Files/Java/jdk-17"),
    ]
    jdk_home = next((p for p in candidates if p.exists()), candidates[0])
    android_sdk = Path(os.environ["LOCALAPPDATA"]) / "Android" / "Sdk"

    env = os.environ.copy()
    env["JAVA_HOME"] = str(jdk_home)
    env["ANDROID_HOME"] = str(android_sdk)
    env["ANDROID_SDK_ROOT"] = str(android_sdk)
    env["PATH"] = f"{jdk_home / 'bin'}{os.pathsep}{env.get('PATH', '')}"

    print("[*] Building RidgeWatch Native Companion APK...")
    print(f"[*] JAVA_HOME:    {jdk_home}")
    print(f"[*] ANDROID_HOME: {android_sdk}")
    print(f"[*] Working Dir:  {root}\n")

    gradlew = root / "gradlew.bat"
    cmd = [str(gradlew), "assembleDebug", "--stacktrace"]

    res = subprocess.run(cmd, cwd=root, env=env)
    if res.returncode == 0:
        apk_path = root / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk"
        if apk_path.exists():
            import shutil
            dest = root.parent / "frontend" / "apk" / "ridgewatch-companion.apk"
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(apk_path, dest)
            print("\n=======================================================")
            print("[SUCCESS] BUILD SUCCESSFUL!")
            print(f"APK Location: {apk_path} ({apk_path.stat().st_size} bytes)")
            print(f"Copied to:    {dest}")
            print("=======================================================\n")
        else:
            print("\n[!] Gradle succeeded, checking output directory for APK...")
    else:
        print(f"\n[FAILURE] Build failed with exit code {res.returncode}")
    
    sys.exit(res.returncode)

if __name__ == "__main__":
    main()
