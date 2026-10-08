# Dry Bean dataset attribution

Dry Bean [Dataset]. (2020). UCI Machine Learning Repository, dataset ID 602.
DOI: [10.24432/C50S4B](https://doi.org/10.24432/C50S4B).
Source and license: [official UCI dataset page](https://archive.ics.uci.edu/dataset/602/dry+bean+dataset).

The dataset is distributed under **Creative Commons Attribution 4.0 International**
([CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)). Retain this attribution
with copies and derived works; indicate modifications when applicable. The original
ZIP/ARFF bytes in the runtime package are unchanged. BeanFeature Lab's derived
validation metadata and research artifacts are identified separately in its manifest.

Related paper: Koklu, M. and Ozkan, I. A. (2020), *Multiclass classification of dry
beans using computer vision and machine learning techniques*, Computers and
Electronics in Agriculture. This application does not imply endorsement by UCI
or the original researchers.

Canonical scientific schema follows the official ARFF, including `AspectRation`,
`roundness`, and `DERMASON`; some descriptions on the UCI web page use different
spellings. Byte identities are preserved:

- Official ZIP SHA-256: `0a64eff5be87f48c3dbbfc0a12a56c5d5b5167ef8e61cd45d69b3e7c7130c06f`.
- Official ARFF SHA-256: `b2a4a76a2aedfb8ed415adfc1bfc70b5f202cb00cb72e500766e364c14834014`.

PDF fonts are DejaVu Sans/Mono supplied by the pinned Matplotlib distribution,
with their license retained in that dependency. They are embedded in generated
PDFs; no macOS font is required. Web fonts are the pinned `@fontsource/golos-text`
package. Their licenses do not replace the dataset license.
