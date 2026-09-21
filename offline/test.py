#!/usr/bin/env python3
"""Compile and exercise the local installer without Minecraft, Gradle, or networking."""
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parent.parent
output = root / 'build/offline-tests'
output.mkdir(parents=True, exist_ok=True)
subprocess.run(['javac', '--release', '21', '-d', str(output),
    str(root / 'common/src/main/java/com/cinemamod/mcef/offline/OfflineRuntime.java'),
    str(root / 'offline/OfflineRuntimeTest.java')], check=True)
subprocess.run(['java', '-cp', str(output), 'com.cinemamod.mcef.offline.OfflineRuntimeTest'], check=True)
