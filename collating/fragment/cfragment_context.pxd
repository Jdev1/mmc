cdef extern from *:
    ctypedef char * const_char_ptr "const char*"

cdef extern from "include/fragment_classifier.h":
    ctypedef struct FragmentClassifier:
        pass

    FragmentClassifier * fragment_classifier_new(char * pFilename,
            unsigned int pFragmentSize)
    void fragment_classifier_free(FragmentClassifier * pFragmentClassifier)
    int fragment_classifier_classify(
            FragmentClassifier * pFragmentClassifier,
            unsigned char * pBuf,
            int pLen)