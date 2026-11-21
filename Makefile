include $(TOPDIR)/rules.mk

PKG_NAME:=brother-brscan2
PKG_VERSION:=0.2.5
PKG_RELEASE:=28

PKG_SOURCE:=brscan2-src-$(PKG_VERSION)-1.tar.gz
PKG_SOURCE_SUBDIR:=brscan2-src-$(PKG_VERSION)-1/brscan
PKG_SOURCE_URL:=https://download.brother.com/welcome/dlf006820/
PKG_HASH:=5069967f5a80c1a4bd1e483eb05f880d9aa846509f7c9e8ce5fd8285bd66f00b
PKG_BUILD_DIR:=$(BUILD_DIR)/brscan2-src-$(PKG_VERSION)-1
BRSCAN_DIR:=$(PKG_BUILD_DIR)/brscan
PKG_BUILD_DEPENDS:=libusb-compat
PKG_BUILD_PARALLEL:=1

include $(INCLUDE_DIR)/package.mk

define Package/brother-brscan2
  SECTION:=utils
  CATEGORY:=Utilities
  TITLE:=Brother brscan2 backend for MFC-7420
  URL:=https://support.brother.com/g/b/downloadlist.aspx?c=us_ot&lang=en&os=128&prod=mfc7420_all
  DEPENDS:=+libsane +libusb-compat
endef

define Package/brother-brscan2/description
 Brother brscan2 SANE backend for USB scanners, including the MFC-7420.
 The proprietary x86 shared libraries are replaced by portable C sources.
endef

define Package/brother-brscan2/conffiles
/etc/sane.d/brother2-geometry.conf
endef

define Build/Prepare
	$(call Build/Prepare/Default)
	find $(BRSCAN_DIR) -type f \( -name '*.lo' -o -name '*.o' -o -name '*.a' -o -name '*.so' -o -name '*.so.*' \) -delete
	find $(BRSCAN_DIR) -type d -name .libs -prune -exec rm -rf {} +
	$(CP) ./files/libbrscandec/. $(BRSCAN_DIR)/libbrscandec2/
	$(CP) ./files/libbrcolm/. $(BRSCAN_DIR)/libbrcolm2/
	$(RM) $(BRSCAN_DIR)/libbrscandec2/*.so* $(BRSCAN_DIR)/libbrcolm2/*.so*
	ln -sfn backend_brscan2 $(BRSCAN_DIR)/backend_brscan
	ln -sfn backend_src $(BRSCAN_DIR)/libsane-brother
	$(SED) 's,/usr/local/Brother/sane/,/usr/share/sane/brother/,g' $(BRSCAN_DIR)/backend_src/brother.h $(BRSCAN_DIR)/backend_src/brother_advini.h $(BRSCAN_DIR)/backend_src/brother_log.c
	$(SED) 's/(ltime%1000)/(long)(ltime%1000)/; s/vsprintf(/vsnprintf(/; s/(LPSTR)szStrBuff,/(LPSTR)szStrBuff, sizeof(szStrBuff),/; s/sprintf(szStrBuff,/snprintf(szStrBuff, sizeof(szStrBuff),/; s/fwrite( szStrBuff, sizeof(char), dwStrLen,/fwrite( szStrBuff, sizeof(char), strlen(szStrBuff),/; s/char   szStrBuff\[ LOGSTRMAXLEN \];/char   szStrBuff[ LOGSTRMAXLEN ] = {0};/' $(BRSCAN_DIR)/backend_src/brother_log.c
	$(SED) 's/i < nCmdLen ; i++, lpszCmd++/i < nCmdLen \&\& lpCmdStr < szStrBuff + sizeof(szStrBuff) - 2 ; i++, lpszCmd++/; s/\*lpszCmd++ = '\''\.'\'';/\*lpCmdStr++ = '\''\.'\'';/' $(BRSCAN_DIR)/backend_src/brother_log.c
	$(SED) '/#include <curses.h>/d' $(BRSCAN_DIR)/backend_src/brother_advini.c
	$(SED) '/#include <stdlib.h>/a\\#include <stdint.h>' $(BRSCAN_DIR)/backend_src/brother_bugchk.c
	$(SED) 's/if (ptr == NULL || (unsigned int)ptr < 100UL)/if (ptr == NULL) return; if ((uintptr_t)ptr < 100UL)/' $(BRSCAN_DIR)/backend_src/brother_bugchk.c
	$(SED) '/^#define __NETSCANL___/a\\#include <sys/time.h>' $(BRSCAN_DIR)/backend_src/brother_netdev.h
	$(SED) 's/if ( 1 == isfdtype(fileno(stderr), S_IFSOCK) )/if ( 0 )/' $(BRSCAN_DIR)/sanei/sanei_init_debug.c
	cd $(BRSCAN_DIR) && ./configure --host=$(GNU_TARGET_NAME) --prefix=/usr --libdir=/usr/lib --sysconfdir=/etc --datadir=/usr/share
	$(SED) 's/-lnsl //g' $(BRSCAN_DIR)/backend_brscan2/Makefile
	$(SED) '/^LIBLIB_FUNCS =/,+1d' $(BRSCAN_DIR)/backend_brscan2/Makefile
	$(SED) 's,../sanei/sanei_init_debug.lo,sanei_init_debug.lo,g; s,../sanei/sanei_config.lo,sanei_config.lo,g; s,../sanei/sanei_constrain_value.lo,sanei_constrain_value.lo,g' $(BRSCAN_DIR)/backend_brscan2/Makefile
endef

define Build/Compile
	$(TARGET_CC) $(TARGET_CFLAGS) $(TARGET_CPPFLAGS) -fPIC -shared \
		-Wl,-soname,libbrscandec2.so.1 \
		-I$(BRSCAN_DIR)/libbrscandec2 \
		-o $(BRSCAN_DIR)/libbrscandec2/libbrscandec2.so.1.0.0 \
		$(BRSCAN_DIR)/libbrscandec2/brother_bugchk.c \
		$(BRSCAN_DIR)/libbrscandec2/brother_scandec.c \
		$(BRSCAN_DIR)/libbrscandec2/brother_chreso.c
	$(TARGET_CC) $(TARGET_CFLAGS) $(TARGET_CPPFLAGS) -fPIC -shared \
		-Wl,-soname,libbrcolm2.so.1 -lm \
		-I$(BRSCAN_DIR)/libbrcolm2 \
		-o $(BRSCAN_DIR)/libbrcolm2/libbrcolm2.so.1.0.0 \
		$(BRSCAN_DIR)/libbrcolm2/brcolm.c
	cd $(BRSCAN_DIR)/backend_brscan2 && \
		$(SHELL) mk_backend link && \
		ln -sfn ../sanei/sanei_init_debug.c sanei_init_debug.c && \
		ln -sfn ../sanei/sanei_config.c sanei_config.c && \
		ln -sfn ../sanei/sanei_constrain_value.c sanei_constrain_value.c && \
		$(MAKE) CC="$(TARGET_CC)" \
		CFLAGS="$(TARGET_CFLAGS) -fPIC" \
		CPPFLAGS="$(TARGET_CPPFLAGS) -D_GNU_SOURCE -DPATH_SANE_CONFIG_DIR=\\\"/etc/sane.d\\\" -DPATH_SANE_DATA_DIR=\\\"/usr/share\\\" -DV_MAJOR=1 -DV_MINOR=0" \
		LDFLAGS="$(TARGET_LDFLAGS) -Wl,--no-as-needed -lpthread" BACKENDLIBS="-lusb-0.1 -lm -ldl" \
		libsane-brother2.la && \
	$(TARGET_CC) -shared $(TARGET_LDFLAGS) -Wl,--no-as-needed \
		-Wl,-soname,libsane-brother2.so.1 \
		-o $(BRSCAN_DIR)/backend_brscan2/.libs/libsane-brother2.so.1.0.7 \
		$(BRSCAN_DIR)/backend_brscan2/brother2.lo \
		$(BRSCAN_DIR)/backend_brscan2/brother2-s.lo \
		$(BRSCAN_DIR)/backend_brscan2/sane_strstatus.lo \
		$(BRSCAN_DIR)/backend_brscan2/sanei_init_debug.lo \
		$(BRSCAN_DIR)/backend_brscan2/sanei_config.lo \
		$(BRSCAN_DIR)/backend_brscan2/sanei_constrain_value.lo \
		-lusb -lm -ldl -lpthread
endef

define Package/brother-brscan2/install
	$(INSTALL_DIR) $(1)/usr/lib/sane $(1)/usr/lib $(1)/usr/share/sane/brother/GrayCmData/ALL $(1)/usr/share/sane
	$(INSTALL_BIN) $(BRSCAN_DIR)/backend_brscan2/.libs/libsane-brother2.so.1.0.7 $(1)/usr/lib/sane/
	$(LN) libsane-brother2.so.1.0.7 $(1)/usr/lib/sane/libsane-brother2.so.1
	$(INSTALL_BIN) $(BRSCAN_DIR)/libbrscandec2/libbrscandec2.so.1.0.0 $(1)/usr/lib/
	$(LN) libbrscandec2.so.1.0.0 $(1)/usr/lib/libbrscandec2.so.1
	$(LN) libbrscandec2.so.1 $(1)/usr/lib/libbrscandec2.so
	$(INSTALL_BIN) $(BRSCAN_DIR)/libbrcolm2/libbrcolm2.so.1.0.0 $(1)/usr/lib/
	$(LN) libbrcolm2.so.1.0.0 $(1)/usr/lib/libbrcolm2.so.1
	$(LN) libbrcolm2.so.1 $(1)/usr/lib/libbrcolm2.so
	$(INSTALL_DATA) $(BRSCAN_DIR)/mk_package/Brsane2.ini $(1)/usr/share/sane/brother/
	$(INSTALL_DATA) ./files/GrayCmData/ALL/brmsl08f.cm $(1)/usr/share/sane/brother/GrayCmData/ALL/
	$(INSTALL_DATA) ./files/04f9-brscan2.usbid $(1)/usr/share/sane/
	$(INSTALL_DIR) $(1)/etc/sane.d/dll.d
	$(INSTALL_DATA) ./files/brother2-geometry.conf $(1)/etc/sane.d/
	$(INSTALL_DATA) ./files/brother2.conf $(1)/etc/sane.d/dll.d/
endef

$(eval $(call BuildPackage,brother-brscan2))
