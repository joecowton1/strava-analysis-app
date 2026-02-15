#!/usr/bin/env python3
"""
Batch processor: Invokes the worker repeatedly to process all queued events.
Runs much faster than calling the worker manually for each ride.
"""

import os
import sys
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

WORKER_URL = os.environ.get("WORKER_URL", "https://strava-worker-ftxt43xj5a-nw.a.run.app")
MAX_WORKERS = int(os.environ.get("MAX_WORKERS", "5"))  # Process up to 5 rides in parallel
MAX_ITERATIONS = int(os.environ.get("MAX_ITERATIONS", "600"))

def invoke_worker():
    """Invoke the worker once. Returns True if work was done, False if no work."""
    try:
        req = urllib.request.Request(WORKER_URL, method='GET')
        with urllib.request.urlopen(req, timeout=120) as response:
            body = response.read().decode('utf-8')
            if "No queued events" in body or "No work" in body:
                return False
            return True
    except urllib.error.HTTPError as e:
        print(f"✗ HTTP {e.code}", flush=True)
        return False
    except Exception as e:
        print(f"✗ Error: {e}", flush=True)
        return False

def main():
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  Strava Worker - Batch Processor")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"\nWorker URL: {WORKER_URL}")
    print(f"Max parallel workers: {MAX_WORKERS}")
    print(f"Max iterations: {MAX_ITERATIONS}")
    print("\nProcessing queued rides...\n")
    
    processed = 0
    no_work_count = 0
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        iteration = 0
        while iteration < MAX_ITERATIONS:
            # Submit a batch of worker invocations
            futures = []
            for _ in range(MAX_WORKERS):
                if iteration >= MAX_ITERATIONS:
                    break
                futures.append(executor.submit(invoke_worker))
                iteration += 1
            
            # Wait for all to complete
            batch_had_work = False
            for future in as_completed(futures):
                had_work = future.result()
                if had_work:
                    processed += 1
                    batch_had_work = True
                    print(f"✓ Processed ride #{processed}", flush=True)
                else:
                    no_work_count += 1
            
            # If none of the workers found work, we're done
            if not batch_had_work:
                if no_work_count >= MAX_WORKERS * 2:
                    print("\n✅ All queued events processed!")
                    break
            else:
                no_work_count = 0
            
            # Brief pause between batches
            time.sleep(0.5)
    
    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  Summary")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"\nTotal rides processed: {processed}")
    print("\nCheck your dashboard at: https://strava-frontend-101613509672.europe-west2.run.app\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠ Interrupted by user")
        sys.exit(1)
