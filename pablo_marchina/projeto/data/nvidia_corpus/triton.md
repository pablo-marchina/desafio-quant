<!DOCTYPE html
  PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
   <head>
      
      <script src="https://cdn.cookielaw.org/scripttemplates/otSDKStub.js" data-document-language="true" type="text/javascript" charset="UTF-8" data-domain-script="3e2b62ff-7ae7-4ac5-87c8-d5949ecafff5"></script>
      <script type="text/javascript">
      function OptanonWrapper() {       
        var event = new Event('bannerLoaded');
        window.dispatchEvent(event);
      };
      </script>
      
      <script type="text/javascript" src="https://images.nvidia.com/aem-dam/Solutions/ot-js/ot-custom.js"></script>
      <meta http-equiv="X-UA-Compatible" content="IE=edge"></meta>
      <meta charset="utf-8"></meta>
      <title>NVIDIA Deep Learning Triton Inference Server Documentation</title>
      <link rel="stylesheet" type="text/css" href="common/formatting/site.css"></link>
      <!--[if lt IE 9]>
      <script src="common/formatting/html5shiv-printshiv.min.js"></script>
      <![endif]-->
      <script src="//assets.adobedtm.com/5d4962a43b79/c1061d2c5e7b/launch-191c2462b890.min.js"></script>
      <script type="text/javascript" charset="utf-8" src="common/formatting/jquery.min.js"></script>
      <script type="text/javascript" charset="utf-8" src="common/formatting/jquery.ba-hashchange.min.js"></script>
      <script type="text/javascript" src="search/htmlFileList.js"></script>
      <script type="text/javascript" src="search/htmlFileInfoList.js"></script>
      <script type="text/javascript" src="search/nwSearchFnt.min.js"></script>
      <script type="text/javascript" src="search/stemmers/en_stemmer.min.js"></script>
      <script type="text/javascript" src="search/index-1.js"></script>
      <script type="text/javascript" src="search/index-2.js"></script>
      <script type="text/javascript" src="search/index-3.js"></script>
      </head>
   <body>
      <header id="header">
         <span id="company">NVIDIA</span><span id="site-title">NVIDIA Deep Learning Triton Inference Server Documentation</span><form id="search" method="get" action="search">
            <input type="text" name="search-text"></input><fieldset id="search-location">
               <legend>Search In:</legend>
               <label><input type="radio" name="search-type" value="site"></input>Entire Site</label>
               <label><input type="radio" name="search-type" value="document"></input>Just This Document</label></fieldset>
            <button type="reset">clear search</button>
            <button id="submit" type="submit">search</button></form>
      </header>
      <div id="site-content">
         <nav id="site-nav">
            <div class="category"><a href="#">Getting Started</a></div>
            <ul>
               <li><a href="release-notes/index.html" title="The actual inference server is packaged in the Triton Inference Server container. This document provides information about how to set up and run the Triton inference server container, from the prerequisites to running the container. The release notes also provide a list of key features, packaged software in the container, software enhancements and improvements, known issues, and how to run the Triton Inference Server 2.43.0 (V2 API) for the 24.02 and earlier releases. The Triton inference server container is released monthly to provide you with the latest NVIDIA deep learning software libraries and GitHub code contributions that have been sent upstream. The libraries and contributions have all been tested, tuned, and optimized.">Release Notes</a></li>
            </ul>
            <div class="category"><a href="#inference-server">Inference Server</a></div>
            <ul>
               <li><a href="user-guide/docs/index.html" title="This Triton Inference Server documentation focuses on the Triton inference server and its benefits. The inference server is included within the inference server container. This guide provides step-by-step instructions for pulling and running the Triton inference server container, along with the details of the model store and the inference API.">Documentation - Latest Release</a></li>
               <li><a href="master-user-guide/index.html" title="This is the GitHub pre-release documentation for Triton inference server. This documentation is an unstable documentation preview for developers and is updated continuously to be in sync with the Triton inference server in GitHub.">Documentation – Pre-release</a></li>
            </ul>
            <div class="category"><a href="#licenses">Licenses</a></div>
            <ul>
               <li><a href="sla/index.html" title="This document is the Software License Agreement (SLA) for NVIDIA Triton Inference Server. The following contains specific license terms and conditions for NVIDIA Triton Inference Server. By accepting this agreement, you agree to comply with all the terms and conditions applicable to the specific product(s) included herein.">SLA</a></li>
               <li><a href="bsd/index.html" title="This document is the Berkeley Software Distribution (BSD) license for NVIDIA Triton Inference Server. The following contains specific license terms and conditions for NVIDIA Triton Inference Server open sourced. By accepting this agreement, you agree to comply with all the terms and conditions applicable to the specific product(s) included herein.">BSD License</a></li>
            </ul>
            <div class="category"><a href="#archives">Archives</a></div>
            <ul>
               <li><a href="archives/index.html" title="This Archives document provides access to previously released Triton inference server documentation versions.">Documentation Archives</a></li>
            </ul>
         </nav>
         <div id="resize-nav"></div>
         <nav id="search-results">
            <h2>Search Results</h2>
            <ol></ol>
         </nav>
         <div id="contents-container">
            <article id="contents">
               <div id="release-info" align="right">NVIDIA Deep Learning Triton Inference Server Documentation
                  
                  
                  
                  -
                  Last updated June 24, 2026
                  -
                  <a href="mailto:dldocs@nvidia.com?subject=NVIDIA Deep Learning Triton Inference Server Documentation Feedback: NVIDIA Deep Learning Triton Inference Server Documentation">Send Feedback</a>
                  -
                  
               </div>
               <header>
                  <h1>NVIDIA Triton Inference Server</h1>
               </header>
               <hr></hr>
               <dl class="landing-page">
                  <dt><a href="release-notes/index.html">Release Notes</a></dt>
                  <dd>The actual inference server is packaged in the Triton Inference
                     Server container. This document provides information about how to set up and run the
                     Triton inference server container, from the prerequisites to running the container. The
                     release notes also provide a list of key features, packaged software in the container,
                     software enhancements and improvements, known issues, and how to run the Triton
                     Inference Server 2.43.0 (V2 API) for the 24.02 and earlier releases. The Triton
                     inference server container is released monthly to provide you with the latest NVIDIA
                     deep learning software libraries and GitHub code contributions that have been sent
                     upstream. The libraries and contributions have all been tested, tuned, and
                     optimized.
                  </dd>
               </dl>
               <h2 id="inference-server">Inference Server</h2>
               <hr></hr>
               <dl class="landing-page">
                  <dt><a href="user-guide/docs/index.html">Documentation - Latest Release</a></dt>
                  <dd>This Triton Inference Server documentation focuses on the Triton inference server and
                     its benefits. The inference server is included within the inference server container. This
                     guide provides step-by-step instructions for pulling and running the Triton inference server
                     container, along with the details of the model store and the inference API.
                  </dd>
                  <dt><a href="master-user-guide/index.html">Documentation – Pre-release</a></dt>
                  <dd>This is the GitHub pre-release documentation for Triton inference server. This
                     documentation is an unstable documentation preview for developers and is updated
                     continuously to be in sync with the Triton inference server in GitHub.
                  </dd>
               </dl>
               <h2 id="licenses">Licenses</h2>
               <hr></hr>
               <dl class="landing-page">
                  <dt><a href="sla/index.html">SLA</a></dt>
                  <dd>This document is the Software License Agreement (SLA) for NVIDIA
                     Triton Inference Server. The following contains specific license terms and conditions
                     for NVIDIA Triton Inference Server. By accepting this agreement, you agree to comply
                     with all the terms and conditions applicable to the specific product(s) included herein. 
                  </dd>
                  <dt><a href="bsd/index.html">BSD License</a></dt>
                  <dd>This document is the Berkeley Software Distribution (BSD) license
                     for NVIDIA Triton Inference Server. The following contains specific license terms and
                     conditions for NVIDIA Triton Inference Server open sourced. By accepting this agreement,
                     you agree to comply with all the terms and conditions applicable to the specific
                     product(s) included herein. 
                  </dd>
               </dl>
               <h2 id="archives">Archives</h2>
               <hr></hr>
               <dl class="landing-page">
                  <dt><a href="archives/index.html">Documentation Archives</a></dt>
                  <dd>This Archives document provides access to previously released
                     Triton inference server documentation versions. 
                  </dd>
               </dl>
            </article>
            <footer id="footer"><img src="./common/formatting/NVIDIA-LogoBlack.svg"></img><div><a href="https://www.nvidia.com/en-us/about-nvidia/privacy-policy/" target="_blank">Privacy Policy</a> |
                  <a href="https://www.nvidia.com/en-us/privacy-center/" target="_blank">Manage My Privacy</a> |
                  <a href="https://www.nvidia.com/en-us/preferences/email-preferences/" target="_blank">Do Not Sell or Share My Data</a> |
                  <a href="https://www.nvidia.com/en-us/about-nvidia/terms-of-service/" target="_blank">Terms of Service</a> |
                  <a href="https://www.nvidia.com/en-us/about-nvidia/accessibility/" target="_blank">Accessibility</a> |
                  <a href="https://www.nvidia.com/en-us/about-nvidia/company-policies/" target="_blank">Corporate Policies</a> |
                  <a href="https://www.nvidia.com/en-us/product-security/" target="_blank">Product Security</a> |
                  <a href="https://www.nvidia.com/en-us/contact/" target="_blank">Contact</a></div>
               <div class="copyright">Copyright © 2026 NVIDIA Corporation</div>
            </footer>
         </div>
      </div>
      <script language="JavaScript" type="text/javascript" charset="utf-8" src="common/formatting/common.min.js"></script>
      <script type="text/javascript">_satellite.pageBottom();</script>
      <script type="text/javascript">var switchTo5x=true;</script><script type="text/javascript">stLight.options({publisher: "998dc202-a267-4d8e-bce9-14debadb8d92", doNotHash: false, doNotCopy: false, hashAddressBar: false});</script></body>
</html>