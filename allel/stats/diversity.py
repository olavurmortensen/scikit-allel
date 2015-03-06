# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, division


import numpy as np


from allel.model import SortedIndex
from allel.util import asarray_ndim, ignore_invalid, check_arrays_aligned
from allel.stats.window import windowed_statistic, per_base


def mean_pairwise_diversity(ac, fill=np.nan):
    """Calculate for each variant the mean number of pairwise differences
    between haplotypes within a single population.

    Parameters
    ----------

    ac : array_like, int, shape (n_variants, n_alleles)
        Allele counts array.
    fill : float
        Use this value where there are no pairs to compare (e.g.,
        all allele calls are missing).

    Returns
    -------

    mpd : ndarray, float, shape (n_variants,)

    Notes
    -----

    The values returned by this function can be summed over a genome
    region and divided by the number of accessible bases to estimate
    nucleotide diversity, a.k.a. *pi*.

    Examples
    --------

    >>> import allel
    >>> h = allel.model.HaplotypeArray([[0, 0, 0, 0],
    ...                                 [0, 0, 0, 1],
    ...                                 [0, 0, 1, 1],
    ...                                 [0, 1, 1, 1],
    ...                                 [1, 1, 1, 1],
    ...                                 [0, 0, 1, 2],
    ...                                 [0, 1, 1, 2],
    ...                                 [0, 1, -1, -1]])
    >>> ac = h.count_alleles()
    >>> allel.stats.mean_pairwise_diversity(ac)
    array([ 0.        ,  0.5       ,  0.66666667,  0.5       ,  0.        ,
            0.83333333,  0.83333333,  1.        ])

    See Also
    --------

    sequence_diversity, windowed_diversity

    """

    # This function calculates the mean number of pairwise differences
    # between haplotypes within a single population, generalising to any number
    # of alleles.

    # check inputs
    ac = asarray_ndim(ac, 2)

    # total number of haplotypes
    an = np.sum(ac, axis=1)

    # total number of pairwise comparisons for each variant:
    # (an choose 2)
    n_pairs = an * (an - 1) / 2

    # number of pairwise comparisons where there is no difference:
    # sum of (ac choose 2) for each allele (i.e., number of ways to
    # choose the same allele twice)
    n_same = np.sum(ac * (ac - 1) / 2, axis=1)

    # number of pairwise differences
    n_diff = n_pairs - n_same

    # mean number of pairwise differences, accounting for cases where
    # there are no pairs
    with ignore_invalid():
        mpd = np.where(n_pairs > 0, n_diff / n_pairs, fill)

    return mpd


def _resize_dim2(a, l):
    newshape = a.shape[0], l
    b = np.zeros(newshape, dtype=a.dtype)
    b[:, :a.shape[1]] = a
    return b


def mean_pairwise_divergence(ac1, ac2, an1=None, an2=None, fill=np.nan):
    """Calculate for each variant the mean number of pairwise differences
    between haplotypes from two different populations.

    Parameters
    ----------

    ac1 : array_like, int, shape (n_variants, n_alleles)
        Allele counts array from the first population.
    ac2 : array_like, int, shape (n_variants, n_alleles)
        Allele counts array from the second population.
    an1 : array_like, int, shape (n_variants,), optional
        Allele numbers for the first population. If not provided, will be
        calculated from `ac1`.
    an2 : array_like, int, shape (n_variants,), optional
        Allele numbers for the second population. If not provided, will be
        calculated from `ac2`.
    fill : float
        Use this value where there are no pairs to compare (e.g.,
        all allele calls are missing).

    Returns
    -------

    mpd : ndarray, float, shape (n_variants,)

    Notes
    -----

    The values returned by this function can be summed over a genome
    region and divided by the number of accessible bases to estimate
    nucleotide divergence between two populations, a.k.a. *Dxy*.

    Examples
    --------

    >>> import allel
    >>> h = allel.model.HaplotypeArray([[0, 0, 0, 0],
    ...                                 [0, 0, 0, 1],
    ...                                 [0, 0, 1, 1],
    ...                                 [0, 1, 1, 1],
    ...                                 [1, 1, 1, 1],
    ...                                 [0, 0, 1, 2],
    ...                                 [0, 1, 1, 2],
    ...                                 [0, 1, -1, -1]])
    >>> ac1 = h.take([0, 1], axis=1).count_alleles()
    >>> ac2 = h.take([2, 3], axis=1).count_alleles()
    >>> allel.stats.mean_pairwise_divergence(ac1, ac2)
    array([ 0.  ,  0.5 ,  1.  ,  0.5 ,  0.  ,  1.  ,  0.75,   nan])

    See Also
    --------

    sequence_divergence, windowed_divergence

    """

    # This function calculates the mean number of pairwise differences
    # between haplotypes from two different populations, generalising to any
    # number of alleles.

    # check inputs
    ac1 = asarray_ndim(ac1, 2)
    ac2 = asarray_ndim(ac2, 2)
    # check lengths match
    check_arrays_aligned(ac1, ac2)
    # ensure same number of alleles in both pops
    if ac1.shape[1] < ac2.shape[1]:
        ac1 = _resize_dim2(ac1, ac2.shape[1])
    elif ac2.shape[1] < ac1.shape[1]:
        ac2 = _resize_dim2(ac2, ac1.shape[1])

    # total number of haplotypes sampled from each population
    if an1 is None:
        an1 = np.sum(ac1, axis=1)
    if an2 is None:
        an2 = np.sum(ac2, axis=1)

    # total number of pairwise comparisons for each variant
    n_pairs = an1 * an2

    # number of pairwise comparisons where there is no difference:
    # sum of (ac1 * ac2) for each allele (i.e., number of ways to
    # choose the same allele twice)
    n_same = np.sum(ac1 * ac2, axis=1)

    # number of pairwise differences
    n_diff = n_pairs - n_same

    # mean number of pairwise differences, accounting for cases where
    # there are no pairs
    with ignore_invalid():
        mpd = np.where(n_pairs > 0, n_diff / n_pairs, fill)

    return mpd


def sequence_diversity(pos, ac, start=None, stop=None,
                       is_accessible=None):
    """Calculate nucleotide diversity within a given region.

    Parameters
    ----------

    pos : array_like, int, shape (n_items,)
        Variant positions, using 1-based coordinates, in ascending order.
    ac : array_like, int, shape (n_variants, n_alleles)
        Allele counts array.
    start : int, optional
        The position at which to start (1-based).
    stop : int, optional
        The position at which to stop (1-based).
    is_accessible : array_like, bool, shape (len(contig),), optional
        Boolean array indicating accessibility status for all positions in the
        chromosome/contig.

    Returns
    -------

    pi : ndarray, float, shape (n_windows,)
        Nucleotide diversity.

    Examples
    --------

    >>> import allel
    >>> g = allel.model.GenotypeArray([[[0, 0], [0, 0]],
    ...                                [[0, 0], [0, 1]],
    ...                                [[0, 0], [1, 1]],
    ...                                [[0, 1], [1, 1]],
    ...                                [[1, 1], [1, 1]],
    ...                                [[0, 0], [1, 2]],
    ...                                [[0, 1], [1, 2]],
    ...                                [[0, 1], [-1, -1]],
    ...                                [[-1, -1], [-1, -1]]])
    >>> ac = g.count_alleles()
    >>> pos = [2, 4, 7, 14, 15, 18, 19, 25, 27]
    >>> pi = allel.stats.sequence_diversity(pos, ac, start=1, stop=31)
    >>> pi
    0.13978494623655915

    """

    # check inputs
    if not isinstance(pos, SortedIndex):
        pos = SortedIndex(pos, copy=False)
    if start is not None or stop is not None:
        loc = pos.locate_range(start, stop)
        pos = pos[loc]
        ac = ac[loc]
    if start is None:
        start = pos[0]
    if stop is None:
        stop = pos[-1]
    is_accessible = asarray_ndim(is_accessible, 1, allow_none=True)

    # calculate mean pairwise diversity
    mpd = mean_pairwise_diversity(ac, fill=0)

    # sum diversity
    mpd_sum = np.sum(mpd)

    # calculate value per base
    if is_accessible is None:
        n_bases = stop - start + 1
    else:
        n_bases = np.count_nonzero(is_accessible[start-1:stop])

    pi = mpd_sum / n_bases
    return pi


def sequence_divergence(pos, ac1, ac2, an1=None, an2=None, start=None,
                        stop=None, is_accessible=None):
    """Calculate nucleotide divergence between two populations within a
    given region.

    Parameters
    ----------

    pos : array_like, int, shape (n_items,)
        Variant positions, using 1-based coordinates, in ascending order.
    ac1 : array_like, int, shape (n_variants, n_alleles)
        Allele counts array for the first population.
    ac2 : array_like, int, shape (n_variants, n_alleles)
        Allele counts array for the second population.
    start : int, optional
        The position at which to start (1-based).
    stop : int, optional
        The position at which to stop (1-based).
    is_accessible : array_like, bool, shape (len(contig),), optional
        Boolean array indicating accessibility status for all positions in the
        chromosome/contig.

    Returns
    -------

    Dxy : ndarray, float, shape (n_windows,)
        Nucleotide divergence.

    Examples
    --------

    Simplest case, two haplotypes in each population::

        >>> import allel
        >>> h = allel.model.HaplotypeArray([[0, 0, 0, 0],
        ...                                 [0, 0, 0, 1],
        ...                                 [0, 0, 1, 1],
        ...                                 [0, 1, 1, 1],
        ...                                 [1, 1, 1, 1],
        ...                                 [0, 0, 1, 2],
        ...                                 [0, 1, 1, 2],
        ...                                 [0, 1, -1, -1],
        ...                                 [-1, -1, -1, -1]])
        >>> h1 = h.subset(haplotypes=[0, 1])
        >>> h2 = h.subset(haplotypes=[2, 3])
        >>> ac1 = h1.count_alleles()
        >>> ac2 = h2.count_alleles()
        >>> pos = [2, 4, 7, 14, 15, 18, 19, 25, 27]
        >>> dxy = sequence_divergence(pos, ac1, ac2, start=1, stop=31)
        >>> dxy
        0.12096774193548387

    """

    # check inputs
    if not isinstance(pos, SortedIndex):
        pos = SortedIndex(pos, copy=False)
    if start is not None or stop is not None:
        loc = pos.locate_range(start, stop)
        pos = pos[loc]
        ac1 = ac1[loc]
        ac2 = ac2[loc]
    if start is None:
        start = pos[0]
    if stop is None:
        stop = pos[-1]
    is_accessible = asarray_ndim(is_accessible, 1, allow_none=True)

    # calculate mean pairwise diversity
    mpd = mean_pairwise_divergence(ac1, ac2, an1=an1, an2=an2, fill=0)

    # sum divergence
    mpd_sum = np.sum(mpd)

    # calculate value per base
    if is_accessible is None:
        n_bases = stop - start + 1
    else:
        n_bases = np.count_nonzero(is_accessible[start-1:stop])

    dxy = mpd_sum / n_bases

    return dxy


def windowed_diversity(pos, ac, size, start=None, stop=None, step=None,
                       windows=None, is_accessible=None, fill=np.nan):
    """Calculate nucleotide diversity in windows over a single
    chromosome/contig.

    Parameters
    ----------

    pos : array_like, int, shape (n_items,)
        Variant positions, using 1-based coordinates, in ascending order.
    ac : array_like, int, shape (n_variants, n_alleles)
        Allele counts array.
    size : int
        The window size (number of bases).
    start : int, optional
        The position at which to start (1-based).
    stop : int, optional
        The position at which to stop (1-based).
    step : int, optional
        The distance between start positions of windows. If not given,
        defaults to the window size, i.e., non-overlapping windows.
    windows : array_like, int, shape (n_windows, 2), optional
        Manually specify the windows to use as a sequence of (window_start,
        window_stop) positions, using 1-based coordinates. Overrides the
        size/start/stop/step parameters.
    is_accessible : array_like, bool, shape (len(contig),), optional
        Boolean array indicating accessibility status for all positions in the
        chromosome/contig.
    fill : object, optional
        The value to use where a window is completely inaccessible.

    Returns
    -------

    pi : ndarray, float, shape (n_windows,)
        Nucleotide diversity in each window.
    windows : ndarray, int, shape (n_windows, 2)
        The windows used, as an array of (window_start, window_stop) positions,
        using 1-based coordinates.
    n_bases : ndarray, int, shape (n_windows,)
        Number of (accessible) bases in each window.
    counts : ndarray, int, shape (n_windows,)
        Number of variants in each window.

    Examples
    --------

    >>> import allel
    >>> g = allel.model.GenotypeArray([[[0, 0], [0, 0]],
    ...                                [[0, 0], [0, 1]],
    ...                                [[0, 0], [1, 1]],
    ...                                [[0, 1], [1, 1]],
    ...                                [[1, 1], [1, 1]],
    ...                                [[0, 0], [1, 2]],
    ...                                [[0, 1], [1, 2]],
    ...                                [[0, 1], [-1, -1]],
    ...                                [[-1, -1], [-1, -1]]])
    >>> ac = g.count_alleles()
    >>> pos = [2, 4, 7, 14, 15, 18, 19, 25, 27]
    >>> pi, windows, n_bases, counts = allel.stats.windowed_diversity(
    ...     pos, ac, size=10, start=1, stop=31
    ... )
    >>> pi
    array([ 0.11666667,  0.21666667,  0.09090909])
    >>> windows
    array([[ 1, 10],
           [11, 20],
           [21, 31]])
    >>> n_bases
    array([10, 10, 11])
    >>> counts
    array([3, 4, 2])

    """

    # check inputs
    if not isinstance(pos, SortedIndex):
        pos = SortedIndex(pos, copy=False)
    is_accessible = asarray_ndim(is_accessible, 1, allow_none=True)

    # calculate mean pairwise diversity
    mpd = mean_pairwise_diversity(ac, fill=0)

    # sum in windows
    mpd_sum, windows, counts = windowed_statistic(
        pos, values=mpd, statistic=np.sum, size=size, start=start, stop=stop,
        step=step, windows=windows, fill=0
    )

    # calculate value per base
    pi, n_bases = per_base(mpd_sum, windows, is_accessible=is_accessible,
                           fill=fill)

    return pi, windows, n_bases, counts


def windowed_divergence(pos, ac1, ac2, size, start=None, stop=None, step=None,
                        is_accessible=None, fill=np.nan):
    """Calculate nucleotide divergence between two populations in windows
    over a single chromosome/contig.

    Parameters
    ----------

    pos : array_like, int, shape (n_items,)
        Variant positions, using 1-based coordinates, in ascending order.
    ac1 : array_like, int, shape (n_variants, n_alleles)
        Allele counts array for the first population.
    ac2 : array_like, int, shape (n_variants, n_alleles)
        Allele counts array for the second population.
    size : int
        The window size (number of bases).
    start : int, optional
        The position at which to start (1-based).
    stop : int, optional
        The position at which to stop (1-based).
    step : int, optional
        The distance between start positions of windows. If not given,
        defaults to the window size, i.e., non-overlapping windows.
    windows : array_like, int, shape (n_windows, 2), optional
        Manually specify the windows to use as a sequence of (window_start,
        window_stop) positions, using 1-based coordinates. Overrides the
        size/start/stop/step parameters.
    is_accessible : array_like, bool, shape (len(contig),), optional
        Boolean array indicating accessibility status for all positions in the
        chromosome/contig.
    fill : object, optional
        The value to use where a window is completely inaccessible.

    Returns
    -------

    Dxy : ndarray, float, shape (n_windows,)
        Nucleotide divergence in each window.
    windows : ndarray, int, shape (n_windows, 2)
        The windows used, as an array of (window_start, window_stop) positions,
        using 1-based coordinates.
    n_bases : ndarray, int, shape (n_windows,)
        Number of (accessible) bases in each window.
    counts : ndarray, int, shape (n_windows,)
        Number of variants in each window.

    Examples
    --------

    Simplest case, two haplotypes in each population::

        >>> import allel
        >>> h = allel.model.HaplotypeArray([[0, 0, 0, 0],
        ...                                 [0, 0, 0, 1],
        ...                                 [0, 0, 1, 1],
        ...                                 [0, 1, 1, 1],
        ...                                 [1, 1, 1, 1],
        ...                                 [0, 0, 1, 2],
        ...                                 [0, 1, 1, 2],
        ...                                 [0, 1, -1, -1],
        ...                                 [-1, -1, -1, -1]])
        >>> h1 = h.subset(haplotypes=[0, 1])
        >>> h2 = h.subset(haplotypes=[2, 3])
        >>> ac1 = h1.count_alleles()
        >>> ac2 = h2.count_alleles()
        >>> pos = [2, 4, 7, 14, 15, 18, 19, 25, 27]
        >>> dxy, windows, n_bases, counts = windowed_divergence(
        ...     pos, ac1, ac2, size=10, start=1, stop=31
        ... )
        >>> dxy
        array([ 0.15 ,  0.225,  0.   ])
        >>> windows
        array([[ 1, 10],
               [11, 20],
               [21, 31]])
        >>> n_bases
        array([10, 10, 11])
        >>> counts
        array([3, 4, 2])

    """

    # check inputs
    pos = SortedIndex(pos, copy=False)
    is_accessible = asarray_ndim(is_accessible, 1, allow_none=True)

    # calculate mean pairwise divergence
    mpd = mean_pairwise_divergence(ac1, ac2, fill=0)

    # sum in windows
    mpd_sum, windows, counts = windowed_statistic(
        pos, values=mpd, statistic=np.sum, size=size, start=start,
        stop=stop, step=step, fill=0
    )

    # calculate value per base
    dxy, n_bases = per_base(mpd_sum, windows, is_accessible=is_accessible,
                            fill=fill)

    return dxy, windows, n_bases, counts