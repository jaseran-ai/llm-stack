import React from 'react';
import {Redirect} from '@docusaurus/router';
import useBaseUrl from '@docusaurus/useBaseUrl';

export default function Home(): React.JSX.Element {
  // Redirect does not prepend baseUrl (e.g. /llm-stack/ on GitHub Pages); useBaseUrl does,
  // including the locale prefix (/fr/).
  return <Redirect to={useBaseUrl('/getting-started/')} />;
}
