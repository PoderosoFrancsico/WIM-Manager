import tempfile
from pathlib import Path
import unittest

from main import mount_folder, parse_images


class CoreTests(unittest.TestCase):
    def test_indices_with_colons_and_unicode(self):
        output = 'Index : 1\nName : Windows: edición especial\nSize : 1,234 bytes\n\nIndex : 3\nName : Recovery\nSize : 567 bytes\n'
        self.assertEqual(parse_images(output), [
            {'index': 1, 'name': 'Windows: edición especial', 'size': '1,234 bytes'},
            {'index': 3, 'name': 'Recovery', 'size': '567 bytes'},
        ])

    def test_no_indices_in_error(self):
        self.assertEqual(parse_images('Error: 87\nThe parameter is incorrect.'), [])

    def test_automatic_folders_never_reuse_existing(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp) / 'mounts'
            image = str(Path(temp) / 'Imagen con espacios.wim')
            first = Path(mount_folder(image, '', str(base)))
            second = Path(mount_folder(image, '', str(base)))
            self.assertEqual(first.name, 'Imagen con espacios')
            self.assertEqual(second.name, 'Imagen con espacios (1)')
            self.assertTrue(first.is_dir())
            self.assertTrue(second.is_dir())

    def test_manual_nonempty_folder_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / 'manual'
            mount_folder('image.wim', str(target), temp)
            (target / 'preservar.txt').write_text('datos')
            with self.assertRaises(ValueError):
                mount_folder('image.wim', str(target), temp)
            self.assertEqual((target / 'preservar.txt').read_text(), 'datos')


if __name__ == '__main__':
    unittest.main()
