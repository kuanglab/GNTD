# GNTD
Reconstructing Spatial Transcriptomes with Graph-guided Neural Tensor Decomposition Informed by Spatial and Functional Relations

![](https://github.com/kuanglab/GNTD/blob/main/GNTD_Workflow.png)

Installation and package requirements
--------------------------------------------------------------------
The python package can be downloaded and run with the following library versions.
```
[python 3.8.12]
[numpy 1.21.5]
[scipy 1.7.3]
[pandas 1.2.3]
[scikit-learn 1.1.3]
[pytorch 1.10.2]
[tensorly 0.6.0]
[scanpy 1.9.1]
[anndata 0.8.0]
```

Data preparation
--------------------------------------------------------------------------------

#### Spatial Transcriptomics Data
Download Visium spatial transcriptomics data from [10x Genomics](https://support.10xgenomics.com/spatial-gene-expression/datasets/) or [spatialLIBD](http://research.libd.org/spatialLIBD/) and make sure these data are organized in the following structure:

        . <data-folder>
        ├── ...
        ├── <tissue-folder>
        │   ├── filtered_feature_bc_matrix
        │   │   ├── barcodes.tsv.gz
        │   │   ├── features.tsv.gz
        │   │   └── matrix.mtx.gz
        │   ├── spatial
        │   │   └── tissue_positions_list.csv
        └── ...
        
Getting started
--------------------------------------------------------------------------------
```python
from GNTD import GNTD
from preprocessing import preprocessing

raw_data_path = "<data-folder>/<tissue-folder>"
PPI_data_path = "<BioGRID-PPI> #tab3 file format, please see details in the link: https://wiki.thebiogrid.org/doku.php/biogrid_tab_version_3.0

rank = 128 # tensor rank
l = 0.1 # weight on graph regularization

expr_tensor, A_g, A_xy, ensembl_ids, gene_names, mapping = preprocessing(raw_data_path, PPI_data_path)
model = GNTD(expr_tensor, A_g, A_xy, rank, l)
expr_tensor_hat = model.impute()
```
