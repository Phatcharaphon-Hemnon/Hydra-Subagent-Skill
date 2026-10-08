"""Retry queue with an off-by-one: the last job is silently dropped."""


def run_queue(jobs):
    completed = []
    index = 0
    while index < len(jobs) - 1:
        job = jobs[index]
        completed.append(f"{job}-done")
        index += 1
    return completed
