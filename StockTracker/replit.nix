{pkgs}: {
  deps = [
    pkgs.pkg-config
    pkgs.arrow-cpp
    pkgs.zlib
    pkgs.xcodebuild
    pkgs.heroku
    pkgs.glibcLocales
    pkgs.postgresql
  ];
}
