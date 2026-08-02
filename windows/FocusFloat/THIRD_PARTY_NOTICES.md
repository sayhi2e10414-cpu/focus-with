# Windows companion third-party notices

FocusFloat for Windows uses these upstream components:

- [Microsoft Windows App SDK](https://github.com/microsoft/WindowsAppSDK),
  licensed under the MIT License.
- [Microsoft ONNX Runtime](https://github.com/microsoft/onnxruntime), licensed
  under the MIT License.
- [ONNX Model Zoo YOLOv3](https://github.com/onnx/models/tree/main/validated/vision/object_detection_segmentation/yolov3),
  including the `yolov3-10.onnx` model, published under the MIT License stated in
  that model's README.

The downloaded model is not redistributed in this repository or in the Windows
build artifact. Its source URL and SHA-256 checksum are pinned in both
`ModelManager.cs` and `download-model.ps1`.
