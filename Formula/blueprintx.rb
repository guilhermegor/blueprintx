class Blueprintx < Formula
  desc "Make + bash scaffolding tool for opinionated Python project skeletons"
  homepage "https://github.com/guilhermegor/blueprintx"
  url "https://github.com/guilhermegor/blueprintx/archive/refs/tags/v0.2.0.tar.gz"
  sha256 "676e84c126cc4203cd9ddc463ec864af2198831ecbaea6ced578fd1985dd2a8b"
  license "MIT"
  version "0.2.0"

  def install
    libexec.install "bin", "templates"

    inreplace libexec/"bin/blueprintx.sh",
              /^BLUEPRINTX_VERSION=".*"/, "BLUEPRINTX_VERSION=\"#{version}\""

    (libexec/"bin").find do |f|
      f.chmod(0755) if f.file? && f.extname == ".sh"
    end

    (bin/"blueprintx").write <<~EOS
      exec "#{libexec}/bin/blueprintx.sh" "$@"
    EOS
  end

  test do
    assert_match "Usage", shell_output("#{bin}/blueprintx --help", 0)
  end
end
