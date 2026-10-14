/** Monotonic generation: even A -> B -> A invalidates the first A request. */
export class ContextEpoch {
    private generation = 0;
    capture(): number { return this.generation; }
    invalidate(): void { this.generation += 1; }
    isCurrent(generation: number): boolean { return generation === this.generation; }
}

/** One refresh policy for polling and explicit refresh; errors cannot outlive their context. */
export async function guardedRefresh(
    context: ContextEpoch,
    alive: () => boolean,
    work: (current: () => boolean) => Promise<void>,
    onError: (error: unknown) => void,
): Promise<void> {
    const epoch = context.capture();
    const current = () => alive() && context.isCurrent(epoch);
    try { await work(current); }
    catch (error) { if (current()) onError(error); }
}
