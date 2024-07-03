FROM quay.io/jupyter/pytorch-notebook:pytorch-2.3.1

RUN pip install pandas rdflib sparqlwrapper 'jupyterlab>=4.1.0,<5.0.0a0' jupyterlab-lsp \
    'python-lsp-server[all]' jupyterlab_code_formatter black isort \
    itables \
    yfiles_jupyter_graphs