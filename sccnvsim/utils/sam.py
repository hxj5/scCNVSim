# sam.py - sam alignment processing.


import multiprocessing
import os
import pysam
import subprocess
from logging import error


def check_read(read, conf):
    if read.mapq < conf.min_mapq:
        return(-2)
    if conf.excl_flag and read.flag & conf.excl_flag:
        return(-3)
    if conf.incl_flag and not read.flag & conf.incl_flag:
        return(-4)
    if conf.no_orphan and read.flag & BAM_FPAIRED and not \
        read.flag & BAM_FPROPER_PAIR:
        return(-5)
    if conf.cell_tag and not read.has_tag(conf.cell_tag):
        return(-11)
    if conf.umi_tag and not read.has_tag(conf.umi_tag):
        return(-12)
    if len(read.positions) < conf.min_len:
        return(-21)
    return(0)


def get_query_bases(read, full_length = False):
    """Qurey bases that are within the alignment.

    Parameters
    ----------
    read : pysam::AlignedSegment object
        The alignment to be queried.
    full_length : bool
        If full_length is set, `None` values will be included for any 
        soft-clipped or unaligned positions within the read. 
        The returned list will thus be of the same length as the read.
    
    Returns
    -------
    list
        A list of bases in qurey sequence that are within the alignment.
    """
    cigar_tuples = read.cigartuples
    if not cigar_tuples:
        return []

    result = []
    pos = 0
    s = read.query_sequence

    for op, l in cigar_tuples:
        if op == BAM_CSOFT_CLIP or op == BAM_CINS:
            if full_length:
                for i in range(0, l):
                    result.append(None)
            pos += l
        elif op == BAM_CMATCH or op == BAM_CEQUAL or op == BAM_CDIFF:
            for i in range(pos, pos + l):
                result.append(s[i])
            pos += l
        # else: do nothing.
    return result


def get_query_qualities(read, full_length=False):
    """Qurey qualities that are within the alignment.

    Parameters
    ----------
    read : pysam::AlignedSegment object
        The alignment to be queried.
    full_length : bool
        If full_length is set, `None` values will be included for any 
        soft-clipped or unaligned positions within the read. 
        The returned list will thus be of the same length as the read.
    
    Returns
    -------
    list
        A list of bases in qurey sequence that are within the alignment.
        Note that the returned qual values are not ASCII-encoded values 
        typically seen in FASTQ or SAM formatted files, no need to 
        substract 33.
    """
    cigar_tuples = read.cigartuples
    if not cigar_tuples:
        return []

    result = []
    pos = 0
    s = read.query_qualities

    for op, l in cigar_tuples:
        if op == BAM_CSOFT_CLIP or op == BAM_CINS:
            if full_length:
                for i in range(0, l):
                    result.append(None)
            pos += l
        elif op == BAM_CMATCH or op == BAM_CEQUAL or op == BAM_CDIFF:
            for i in range(pos, pos + l):
                result.append(s[i])
            pos += l
        # else: do nothing.
    return result


def sam_fetch(sam, chrom, start = None, end = None):
    """Provide a wrapper for sam-fetch method that could automatically
       handle chrom with or without "chr" prefix.

    Parameters
    ----------
    sam : pysam.AlignmentFile object.
        The BAM file object.
    chrom : str
        Chromosome name.
    start : int
        1-based, inclusive. `None` means minimum possible value.
    end : int
        1-based, inclusive. `None` means maximum possible value.

    Returns
    -------
    Iterator
        Iterator if success, `None` otherwise.
    """
    # sam.fetch(): start and stop denote 0-based, half-open intervals.
    if start is not None:
        start = start - 1

    try:   
        itr = sam.fetch(chrom, start, end)
    except:
        pass
    else:
        if itr:
            return itr
    chrom = chrom[3:] if chrom.startswith("chr") else "chr" + chrom
    try:
        itr = sam.fetch(chrom, start, end)
    except:
        return None
    else:
        return itr if itr else None
    

def sam_index(sam_fn_list, ncores = 1):
    if ncores == 1:
        for sam_fn in sam_fn_list:
            pysam.index(sam_fn)
    else:
        pool = multiprocessing.Pool(processes = ncores)
        mp_res = []
        for sam_fn in sam_fn_list:
            mp_res.append(pool.apply_async(
                func = pysam.index,
                args = (sam_fn, ),
                callback = None
            ))
        pool.close()
        pool.join()
    return(0)


def sam_merge(in_fn_list, out_fn):
    pysam.merge("-f", "-o", out_fn, *in_fn_list)


def sam_sort_by_tag(in_bam, tag, out_bam = None, max_mem = "4G", nthreads = 1):
    inplace = False
    if out_bam is None or out_bam == in_bam:
        inplace = True
        out_bam = in_bam + ".tmp.bam"
    try:
        proc = subprocess.Popen(
            args = "samtools sort -m %s -@ %d -t %s -o %s %s" % \
                (max_mem, nthreads - 1, tag, out_bam, in_bam),
            shell = True,
            executable = "/bin/bash",
            stdout = subprocess.PIPE,
            stderr = subprocess.PIPE
        )
        outs, errs = proc.communicate()
        ret = proc.returncode
        if ret != 0:
            error(str(errs.decode()))
            raise RuntimeError
    except:
        error("Error: samtools sort failed (retcode '%s')." % str(ret))
        return(-1)
    if inplace:
        os.replace(out_bam, in_bam)
    return(0)  


BAM_FPAIRED = 1
BAM_FPROPER_PAIR = 2

# Cigar
# reference: https://pysam.readthedocs.io/en/latest/api.html#pysam.AlignedSegment.cigartuples
BAM_CMATCH = 0
BAM_CINS = 1
BAM_CDEL = 2
BAM_CREF_SKIP = 3
BAM_CSOFT_CLIP = 4
BAM_CHARD_CLIP = 5
BAM_CPAD = 6
BAM_CEQUAL = 7
BAM_CDIFF = 8
BAM_CBACK = 9