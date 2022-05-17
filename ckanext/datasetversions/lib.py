from ckan.plugins.toolkit import enqueue_job


def compat_enqueue(fn, queue, args=None):
    u'''
    Enqueue a background job using RQ.
    '''
    enqueue_job(fn, args=args, queue=queue)
