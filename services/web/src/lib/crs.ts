// proj4 definitions for the German municipal CRSs we use.
// Lifted from the QWC2-era stack-config/qwc2-config.json.

import proj4 from 'proj4';
import { register } from 'ol/proj/proj4';

export function registerCRS(): void {
  proj4.defs(
    'EPSG:25832',
    '+proj=utm +zone=32 +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs',
  );
  proj4.defs(
    'EPSG:31466',
    '+proj=tmerc +lat_0=0 +lon_0=6 +k=1 +x_0=2500000 +y_0=0 +ellps=bessel ' +
      '+towgs84=598.1,73.7,418.2,0.202,0.045,-2.455,6.7 +units=m +no_defs',
  );
  proj4.defs(
    'EPSG:31467',
    '+proj=tmerc +lat_0=0 +lon_0=9 +k=1 +x_0=3500000 +y_0=0 +ellps=bessel ' +
      '+towgs84=598.1,73.7,418.2,0.202,0.045,-2.455,6.7 +units=m +no_defs',
  );
  proj4.defs(
    'EPSG:31468',
    '+proj=tmerc +lat_0=0 +lon_0=12 +k=1 +x_0=4500000 +y_0=0 +ellps=bessel ' +
      '+towgs84=598.1,73.7,418.2,0.202,0.045,-2.455,6.7 +units=m +no_defs',
  );
  register(proj4);
}
