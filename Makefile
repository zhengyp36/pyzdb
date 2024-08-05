.PHONY: all clean setup build build_v2 build_v3 

all: setup

clean:
	$(RM) -r build zdb/core/v2/*.so zdb/core/v3/*.so

build: build_v2 build_v3

build_v2:
	python2 setup.py build

build_v3:
	python3 setup.py build

setup: build
	@cp -v build/lib.*-2.*/core.so zdb/core/v2/
	@cp -v build/lib.*-3.*/core.*.so zdb/core/v3/
