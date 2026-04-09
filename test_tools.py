#!/usr/bin/env python3
"""
Test script - verifies all tools work before connecting Claude Code.
Run this AFTER containerlab is deployed and SR Linux has booted.

Usage:
    python3 test_tools.py
"""

import asyncio
import json
import os
import sys

# Set defaults if env vars not set
os.environ.setdefault("DEVICE_HOST", "clab-sheridan-lab-jack-srl")
os.environ.setdefault("DEVICE_USERNAME", "admin")
os.environ.setdefault("DEVICE_PASSWORD", "NokiaSrl1!")

from server import (
    get_device_info,
    get_interfaces,
    get_routes,
    get_running_config,
    get_network_instances,
    configure_interface,
)

PASS = "\033[92m✓ PASS\033[0m"
FAIL = "\033[91m✗ FAIL\033[0m"


async def test_tool(name: str, coro):
    """Run a single tool test."""
    try:
        result = await coro
        data = json.loads(result)
        if data.get("status") == "success":
            print(f"  {PASS}  {name}")
            return True
        else:
            print(f"  {FAIL}  {name}: {data.get('message', 'unknown error')}")
            return False
    except Exception as e:
        print(f"  {FAIL}  {name}: {e}")
        return False


async def test_validation():
    """Test input validation on configure_interface."""
    print("\n── Input Validation Tests ──")
    tests_passed = 0
    total = 4

    # Bad IP
    r = json.loads(await configure_interface("ethernet-1/1", "999.999.999.999", 24))
    if r["status"] == "error" and "Invalid IP" in r["message"]:
        print(f"  {PASS}  Rejects invalid IP")
        tests_passed += 1
    else:
        print(f"  {FAIL}  Should reject invalid IP")

    # Bad interface name
    r = json.loads(await configure_interface("DROP TABLE", "10.0.0.1", 24))
    if r["status"] == "error" and "Invalid interface" in r["message"]:
        print(f"  {PASS}  Rejects invalid interface name")
        tests_passed += 1
    else:
        print(f"  {FAIL}  Should reject invalid interface name")

    # Bad prefix
    r = json.loads(await configure_interface("ethernet-1/1", "10.0.0.1", 33))
    if r["status"] == "error" and "Invalid prefix" in r["message"]:
        print(f"  {PASS}  Rejects invalid prefix length")
        tests_passed += 1
    else:
        print(f"  {FAIL}  Should reject invalid prefix length")

    # Bad admin state
    r = json.loads(await configure_interface("ethernet-1/1", "10.0.0.1", 24, admin_state="yolo"))
    if r["status"] == "error":
        print(f"  {PASS}  Rejects invalid admin state")
        tests_passed += 1
    else:
        print(f"  {FAIL}  Should reject invalid admin state")

    return tests_passed, total


async def main():
    print("=" * 50)
    print("  sheridan-lab-jack Tool Tests")
    print("=" * 50)

    print(f"\n  Device: {os.environ['DEVICE_HOST']}")
    print(f"  User:   {os.environ['DEVICE_USERNAME']}")

    print("\n── Read Tool Tests ──")
    results = []
    results.append(await test_tool("get_device_info", get_device_info()))
    results.append(await test_tool("get_interfaces", get_interfaces()))
    results.append(await test_tool("get_routes", get_routes()))
    results.append(await test_tool("get_running_config", get_running_config()))
    results.append(await test_tool("get_network_instances", get_network_instances()))

    val_passed, val_total = await test_validation()

    read_passed = sum(results)
    total = len(results) + val_total
    passed = read_passed + val_passed

    print(f"\n{'=' * 50}")
    print(f"  Results: {passed}/{total} tests passed")
    print(f"{'=' * 50}")

    if passed < total:
        print("\n  Some tests failed. Check that:")
        print("  1. ContainerLab is running: sudo containerlab inspect")
        print("  2. SR Linux has fully booted (~60s after deploy)")
        print("  3. sshpass is installed: sudo apt install sshpass")
        sys.exit(1)
    else:
        print("\n  All tests passed! Ready for Claude Code.")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
