/** 最大堆（按 score 排序） */
export class MaxHeap<T> {
  private data: Array<{ item: T; score: number }> = [];

  push(item: T, score: number): void {
    this.data.push({ item, score });
    this.bubbleUp(this.data.length - 1);
  }

  pop(): T | undefined {
    if (this.data.length === 0) return undefined;
    const top = this.data[0].item;
    const last = this.data.pop()!;
    if (this.data.length > 0) {
      this.data[0] = last;
      this.siftDown(0);
    }
    return top;
  }

  peek(): T | undefined {
    return this.data[0]?.item;
  }

  get size(): number { return this.data.length; }
  get empty(): boolean { return this.data.length === 0; }

  private bubbleUp(i: number): void {
    while (i > 0) {
      const parent = (i - 1) >> 1;
      if (this.data[parent].score >= this.data[i].score) break;
      [this.data[parent], this.data[i]] = [this.data[i], this.data[parent]];
      i = parent;
    }
  }

  private siftDown(i: number): void {
    const n = this.data.length;
    while (true) {
      let largest = i;
      const l = 2 * i + 1, r = 2 * i + 2;
      if (l < n && this.data[l].score > this.data[largest].score) largest = l;
      if (r < n && this.data[r].score > this.data[largest].score) largest = r;
      if (largest === i) break;
      [this.data[largest], this.data[i]] = [this.data[i], this.data[largest]];
      i = largest;
    }
  }
}
