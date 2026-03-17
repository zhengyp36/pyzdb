# raidz_probe

A SystemTap script used to trace `vdev_raidz_map_alloc` in a running
OpenZFS kernel, capturing the actual RAIDZ stripe layout computed by
the kernel for a given I/O request.

## What it captures

For each I/O, it records:

- Input parameters: offset, size, ashift, dcols, nparity
- Output layout: per-column rc_devidx, rc_offset, rc_size

## Purpose

This was used during pyzdb development to verify that pyzdb's own
RAIDZ layout calculation matches what the kernel actually computes.
The captured data in `raidz.txt` is a sample from that verification.

## Usage

Run on a system with OpenZFS loaded:

    stap raidz.stp