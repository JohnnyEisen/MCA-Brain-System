@echo off
set SPHINXBUILD=sphinx-build
set SOURCEDIR=.
set BUILDDIR=_build

%SPHINXBUILD% -b html %SOURCEDIR% %BUILDDIR%\html
