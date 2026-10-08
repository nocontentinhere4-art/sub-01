#!/bin/sh
# Download the MyConnectome scans the pipeline uses (~900 MB) from OpenNeuro ds000031 into data/.
# Each file lands under NAME.part and is renamed only when curl succeeds, so a cut-off download never looks complete.
# A .nii.gz left behind by an older cut-off run is not a valid gzip and is fetched again.
set -e
B="https://s3.amazonaws.com/openneuro.org/ds000031/sub-01"
mkdir -p data && cd data
for f in \
  ses-2022/anat/sub-01_ses-2022_T1w.nii.gz ses-2022/anat/sub-01_ses-2022_T1w.json \
  ses-2015/dwi/sub-01_ses-2015_acq-g79_dir-pe0_dwi.nii.gz ses-2015/dwi/sub-01_ses-2015_acq-g79_dir-pe0_dwi.bval \
  ses-2015/dwi/sub-01_ses-2015_acq-g79_dir-pe0_dwi.bvec ses-2015/dwi/sub-01_ses-2015_acq-g79_dir-pe0_dwi.json; do
  name=$(basename "$f")
  if [ -f "$name" ]; then
    case "$name" in
      *.nii.gz) gzip -t "$name" 2>/dev/null && continue ;;
      *) continue ;;
    esac
    echo "fetch_data: $name is not a complete gzip, downloading it again" >&2
    rm -f "$name"
  fi
  curl -fSL --retry 3 -o "$name.part" "$B/$f"
  mv "$name.part" "$name"
done
