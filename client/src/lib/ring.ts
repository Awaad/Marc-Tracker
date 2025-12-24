export class RingBuffer<T> {
  private buf: (T | undefined)[];
  private start = 0;
  private size = 0;

  private capacity: number

  constructor(capacity: number) {
    this.capacity = capacity;
    this.buf = new Array<T | undefined>(capacity);
  }

  push(item: T) {
    const idx = (this.start + this.size) % this.capacity;
    this.buf[idx] = item;

    if (this.size < this.capacity) {
      this.size += 1;
    } else {
      // overwrite oldest
      this.start = (this.start + 1) % this.capacity;
    }
  }

  toArray(): T[] {
    const out: T[] = [];
    for (let i = 0; i < this.size; i++) {
      const idx = (this.start + i) % this.capacity;
      const v = this.buf[idx];
      if (v !== undefined) out.push(v);
    }
    return out;
  }

  length(): number {
    return this.size;
  }

  clear() {
    this.buf = new Array<T | undefined>(this.capacity);
    this.start = 0;
    this.size = 0;
  }
}
