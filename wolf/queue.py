
class QueueItem:
    def __init__( self, data ):
        self.data = data
        self.next = None

class Queue:
    """
       Thread-safe (partially) queue. You can insert items into queue in one thread (or some other
       concurrent code, eg. signal handler) and read them in another. Unfortunately, you cannot
       insert items in different concurrent thread or read in two or more places without external
       locking. Pro of this queue is that is doesn't use any system synchronisation routines (like
       mutex or semaphore).
    """

    def __init__( self ):
        self.__first = QueueItem(None)
        self.__last = self.__first

    def __bool__( self ):
        """
            Queue becomes true iff it is not empty.
        """
        return self.__first.next is not None

    def push( self, data ):
        """
            Insert element into queue.
        """
        item = QueueItem(data)
        self.__last.next = item
        self.__last = item

    def pop( self ):
        """
           Remove first element from queue and return it.
        """
        item = self.__first
        assert item.next is not None
        assert item.data is None
        self.__first = item.next
        data, self.__first.data = item.next.data, None
        return data

