#
# NOTE: THIS DOCKERFILE IS GENERATED VIA "apply-templates.sh"
#
# PLEASE DO NOT EDIT IT DIRECTLY.
#

FROM d_base:latest

# ensure local python is preferred over distribution python
ENV PATH=/usr/local/bin:$PATH

# http://bugs.python.org/issue19846
# > At the moment, setting "LANG=C" on a Linux system *fundamentally breaks Python 3*, and that's not OK.
ENV LANG=C.UTF-8

# runtime dependencies
RUN set -eux; \
	apk add --no-cache \
	ca-certificates \
	tzdata \
	;

ENV GPG_KEY=E3FF2839C048B25C084DEBE9B26995E310250568
ENV PYTHON_VERSION=3.8.12

RUN set -eux; \
	\
	apk add --no-cache --virtual .build-deps \
	gnupg \
	tar \
	xz \
	\
	bluez-dev \
	bzip2-dev \
	coreutils \
	dpkg-dev dpkg \
	expat-dev \
	findutils \
	gcc \
	gdbm-dev \
	libc-dev \
	libffi-dev \
	libnsl-dev \
	libtirpc-dev \
	linux-headers \
	make \
	ncurses-dev \
	openssl-dev \
	pax-utils \
	readline-dev \
	sqlite-dev \
	tcl-dev \
	tk \
	tk-dev \
	util-linux-dev \
	xz-dev \
	zlib-dev \
	; \
	\
	wget -O python.tar.xz "https://www.python.org/ftp/python/${PYTHON_VERSION%%[a-z]*}/Python-$PYTHON_VERSION.tar.xz"; \
	wget -O python.tar.xz.asc "https://www.python.org/ftp/python/${PYTHON_VERSION%%[a-z]*}/Python-$PYTHON_VERSION.tar.xz.asc"; \
	GNUPGHOME="$(mktemp -d)"; export GNUPGHOME; \
	gpg --batch --keyserver hkps://keys.openpgp.org --recv-keys "$GPG_KEY"; \
	gpg --batch --verify python.tar.xz.asc python.tar.xz; \
	command -v gpgconf > /dev/null && gpgconf --kill all || :; \
	rm -rf "$GNUPGHOME" python.tar.xz.asc; \
	mkdir -p /usr/src/python; \
	tar --extract --directory /usr/src/python --strip-components=1 --file python.tar.xz; \
	rm python.tar.xz; \
	\
	cd /usr/src/python; \
	gnuArch="$(dpkg-architecture --query DEB_BUILD_GNU_TYPE)"; \
	./configure \
	--build="$gnuArch" \
	--enable-loadable-sqlite-extensions \
	--enable-optimizations \
	--enable-option-checking=fatal \
	--enable-shared \
	--with-system-expat \
	--with-system-ffi \
	--without-ensurepip \
	; \
	nproc="$(nproc)"; \
	make -j "$nproc" \
	# set thread stack size to 1MB so we don't segfault before we hit sys.getrecursionlimit()
	# https://github.com/alpinelinux/aports/commit/2026e1259422d4e0cf92391ca2d3844356c649d0
	EXTRA_CFLAGS="-DTHREAD_STACK_SIZE=0x100000" \
	LDFLAGS="-Wl,--strip-all" \
	; \
	make install; \
	cd /; \
	rm -rf /usr/src/python; \
	\
	find /usr/local -depth \
	\( \
	\( -type d -a \( -name test -o -name tests -o -name idle_test \) \) \
	-o \( -type f -a \( -name '*.pyc' -o -name '*.pyo' -o -name '*.a' \) \) \
	-o \( -type f -a -name 'wininst-*.exe' \) \
	\) -exec rm -rf '{}' + \
	; \
	\
	find /usr/local -type f -executable -not \( -name '*tkinter*' \) -exec scanelf --needed --nobanner --format '%n#p' '{}' ';' \
	| tr ',' '\n' \
	| sort -u \
	| awk 'system("[ -e /usr/local/lib/" $1 " ]") == 0 { next } { print "so:" $1 }' \
	| xargs -rt apk add --no-network --virtual .python-rundeps \
	; \
	apk del --no-network .build-deps; \
	\
	python3 --version

# make some useful symlinks that are expected to exist ("/usr/local/bin/python" and friends)
RUN set -eux; \
	for src in idle3 pydoc3 python3 python3-config; do \
	dst="$(echo "$src" | tr -d 3)"; \
	[ -s "/usr/local/bin/$src" ]; \
	[ ! -e "/usr/local/bin/$dst" ]; \
	ln -svT "/usr/local/bin/$src" "/usr/local/bin/$dst"; \
	done

# if this is called "PIP_VERSION", pip explodes with "ValueError: invalid truth value '<VERSION>'"
ENV PYTHON_PIP_VERSION=21.2.4
# https://github.com/docker-library/python/issues/365
ENV PYTHON_SETUPTOOLS_VERSION=57.5.0
# https://github.com/pypa/get-pip
ENV PYTHON_GET_PIP_URL=https://github.com/pypa/get-pip/raw/2caf84b14febcda8077e59e9b8a6ef9a680aa392/public/get-pip.py
ENV PYTHON_GET_PIP_SHA256=7c5239cea323cadae36083079a5ee6b2b3d56f25762a0c060d2867b89e5e06c5

RUN set -eux; \
	\
	wget -O get-pip.py "$PYTHON_GET_PIP_URL"; \
	echo "$PYTHON_GET_PIP_SHA256 *get-pip.py" | sha256sum -c -; \
	\
	python get-pip.py \
	--disable-pip-version-check \
	--no-cache-dir \
	"pip==$PYTHON_PIP_VERSION" \
	"setuptools==$PYTHON_SETUPTOOLS_VERSION" \
	; \
	pip --version; \
	\
	find /usr/local -depth \
	\( \
	\( -type d -a \( -name test -o -name tests -o -name idle_test \) \) \
	-o \
	\( -type f -a \( -name '*.pyc' -o -name '*.pyo' \) \) \
	\) -exec rm -rf '{}' + \
	; \
	rm -f get-pip.py

# TODO: Let's try it without; we should be able to just restart the matrix
# If we can't get restarting the matrix to work, use this as a fallback.
# Add startup script and set it as entrypoint
# ADD docker-start /docker-start
# RUN chmod +x /docker-start
# RUN apk add --no-cache tmux
# ENTRYPOINT ["/docker-start"]

COPY ping.py /home/ping.py
RUN chmod +x /home/ping.py

WORKDIR /home
CMD ["python", "ping.py"]
