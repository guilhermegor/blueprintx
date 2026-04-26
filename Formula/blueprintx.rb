class Blueprintx < Formula
  desc "Make + bash scaffolding tool for opinionated Python project skeletons"
  homepage "https://github.com/guilhermegor/blueprintx"
  url "https://github.com/guilhermegor/blueprintx/archive/refs/tags/v0.1.3.tar.gz"
  sha256 "517292574a3b9eab35e55b8f1ca08c671596bbd43b1de0205216b0efeeb816e2"
  license "MIT"
  version "0.1.3"

  def install
    # Install bin/ and templates/ under libexec so SCRIPT_DIR-based path navigation works.
    # Scaffold scripts compute BLUEPRINTX_ROOT = $(cd "$SCRIPT_DIR/../.." && pwd):
    #   libexec/bin/scaffold/../../  →  libexec/  ✓
    # All template references ($BLUEPRINTX_ROOT/templates/...) resolve correctly without patching.
    libexec.install "bin", "templates"

    (libexec/"bin").find do |f|
      f.chmod(0755) if f.file? && f.extname == ".sh"
    end

    # exec preserves ${BASH_SOURCE[0]} so SCRIPT_DIR inside blueprintx.sh resolves
    # to libexec/bin rather than the wrapper's location.
    (bin/"blueprintx").write <<~EOS
      #!/usr/bin/env bash
      exec "#{libexec}/bin/blueprintx.sh" "$@"
    EOS
  end

  test do
    assert_match "Usage", shell_output("#{bin}/blueprintx --help", 0)
  end
end
