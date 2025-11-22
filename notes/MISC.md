# Miscellaneous Notes

## Pop vs. Remove
- Why did I use tasks.pop(i) instead of tasks.remove(task) in the delete function?

### How remove() works

remove() searches the list for the first item that equals the argument you pass. With dictionaries, this means Python has to compare dictionary contents:
```py
tasks.remove(task)  # Python: "Find something that equals this dict"
```
This works, but it:

Searches through the list again (we already know the position!)
Relies on dictionary equality comparison

### How pop(i) works

pop(i) just says "remove the item at index i"—no searching, no comparison:
```py
tasks.pop(i)  # Python: "Remove whatever is at position i"
```
We already know the index from enumerate(), so why search again?

**The real-world analogy**

Imagine you're in a library looking for a book. You walk down the aisle, find it at position 47 on the shelf, and then...

pop(i) approach: "Remove the book at position 47" ✓
remove(task) approach: "Go back to the start of the aisle and search for a book with this exact title, author, and ISBN, then remove it" — works, but why?

When it actually matters
For a small list like ours, the performance difference is negligible. But the habit matters:

Clarity of intent: pop(i) says "I know exactly what I'm removing"
Efficiency at scale: With 10,000 tasks, remove() does unnecessary work
Avoiding surprises: What if two tasks somehow had identical content? remove() would only delete the first one it finds (which might not be the one you iterated to)