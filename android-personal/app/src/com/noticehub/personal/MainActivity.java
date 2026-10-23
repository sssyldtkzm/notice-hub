package com.noticehub.personal;

import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.os.Build;
import android.text.InputType;
import android.text.TextUtils;
import android.view.Gravity;
import android.view.View;
import android.view.WindowInsets;
import android.view.WindowInsetsController;
import android.view.WindowManager;
import android.view.DisplayCutout;
import android.graphics.Insets;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;
import android.widget.ScrollView;

/** The personal client uses the server-rendered board, so fixes reach both devices. */
public class MainActivity extends Activity {
    private WebView web;
    private TextView error;
    private String base;
    private SharedPreferences prefs;
    private final int green=Color.rgb(36,86,71);
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        configureSystemBars();
        prefs=getSharedPreferences("personal-connection", MODE_PRIVATE);
        if (!connectIntent(getIntent())) {
            if (prefs.getString("token", "").isEmpty()) settings(); else showBoard();
        }
    }
    @Override protected void onNewIntent(Intent intent) { super.onNewIntent(intent);setIntent(intent);connectIntent(intent); }
    private boolean validBase(String value) {
        Uri u=Uri.parse(value);
        return ("http".equals(u.getScheme())||"https".equals(u.getScheme())) && u.getHost()!=null && u.getUserInfo()==null && u.getQuery()==null && u.getFragment()==null && (u.getPath()==null || u.getPath().isEmpty() || "/".equals(u.getPath()));
    }
    private boolean connectIntent(Intent intent) {
        Uri uri=intent==null?null:intent.getData();
        if(uri==null||!"noticehub-personal".equals(uri.getScheme())||!"connect".equals(uri.getHost()))return false;
        String address=uri.getQueryParameter("base"),token=uri.getQueryParameter("token");
        if(address==null||!validBase(address)||token==null||token.isEmpty()){Toast.makeText(this,"连接信息不完整，请手动填写",Toast.LENGTH_LONG).show();settings();return true;}
        prefs.edit().putString("base",address.replaceAll("/+$", "")).putString("token",token).apply();showBoard();return true;
    }
    private int dp(int value) {return Math.round(value*getResources().getDisplayMetrics().density);}
    private void configureSystemBars() {
        // All versions use one inset owner: the root, never the toolbar/WebView separately.
        if(Build.VERSION.SDK_INT>=30)getWindow().setDecorFitsSystemWindows(false);
        else {
            int flags=View.SYSTEM_UI_FLAG_LAYOUT_STABLE|View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN|View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION|View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR;
            if(Build.VERSION.SDK_INT>=26)flags|=View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR;
            getWindow().getDecorView().setSystemUiVisibility(flags);
        }
        getWindow().setStatusBarColor(Color.TRANSPARENT);
        getWindow().setNavigationBarColor(Build.VERSION.SDK_INT>=26?Color.TRANSPARENT:green);
        if(Build.VERSION.SDK_INT>=28){
            WindowManager.LayoutParams attrs=getWindow().getAttributes();
            attrs.layoutInDisplayCutoutMode=WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES;
            getWindow().setAttributes(attrs);
        }
    }
    private LinearLayout layout() {
        LinearLayout root=new LinearLayout(this);root.setOrientation(LinearLayout.VERTICAL);root.setBackgroundColor(Color.rgb(245,245,239));
        root.setOnApplyWindowInsetsListener((view,insets)->{
            int left,top,right,bottom;
            if(Build.VERSION.SDK_INT>=30){
                Insets safe=insets.getInsets(WindowInsets.Type.systemBars()|WindowInsets.Type.displayCutout()|WindowInsets.Type.ime());
                left=safe.left;top=safe.top;right=safe.right;bottom=safe.bottom;
            }else{
                left=insets.getSystemWindowInsetLeft();top=insets.getSystemWindowInsetTop();right=insets.getSystemWindowInsetRight();bottom=insets.getSystemWindowInsetBottom();
                if(Build.VERSION.SDK_INT>=28){
                    DisplayCutout cutout=insets.getDisplayCutout();
                    if(cutout!=null){left=Math.max(left,cutout.getSafeInsetLeft());top=Math.max(top,cutout.getSafeInsetTop());right=Math.max(right,cutout.getSafeInsetRight());bottom=Math.max(bottom,cutout.getSafeInsetBottom());}
                }
            }
            // Replace padding on every dispatch: rotation/keyboard changes must not accumulate it.
            view.setPadding(left,top,right,bottom);
            if(Build.VERSION.SDK_INT>=30)return WindowInsets.CONSUMED;
            WindowInsets consumed=insets.consumeSystemWindowInsets();
            return Build.VERSION.SDK_INT>=28?consumed.consumeDisplayCutout():consumed;
        });
        setContentView(root);
        root.post(()->{
            root.requestApplyInsets();
            if(Build.VERSION.SDK_INT>=30){
                WindowInsetsController controller=getWindow().getInsetsController();
                if(controller!=null){int light=WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS|WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS;controller.setSystemBarsAppearance(light,light);}
            }
        });
        return root;
    }
    private TextView label(String text,int size) {TextView view=new TextView(this);view.setText(text);view.setTextSize(size);view.setTextColor(green);view.setPadding(0,8,0,12);return view;}
    private void settings() {
        if(web!=null){web.destroy();web=null;}
        LinearLayout frame=layout();ScrollView scroll=new ScrollView(this);scroll.setFillViewport(true);frame.addView(scroll,new LinearLayout.LayoutParams(-1,-1));
        LinearLayout root=new LinearLayout(this);root.setOrientation(LinearLayout.VERTICAL);root.setPadding(dp(20),dp(16),dp(20),dp(16));scroll.addView(root,new ScrollView.LayoutParams(-1,-2));
        root.addView(label("群务台 · 个人版",25));root.addView(label("作业 / 其他事项 / 收藏与高光\n电脑服务和手机 Tailscale 需保持连接。",14));
        root.addView(label("电脑地址",14));EditText address=new EditText(this);address.setSingleLine(true);address.setHint("http://电脑地址:8766");address.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_URI);address.setText(prefs.getString("base",""));root.addView(address);
        root.addView(label("访问 Token",14));EditText key=new EditText(this);key.setSingleLine(true);key.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_PASSWORD);key.setText(prefs.getString("token",""));root.addView(key);
        Button save=new Button(this);save.setText("保存并连接");root.addView(save);save.setOnClickListener(v->{String url=address.getText().toString().trim().replaceAll("/+$", "");String token=key.getText().toString().trim();if(!validBase(url)||token.isEmpty()){Toast.makeText(this,"请填写有效电脑地址和 Token",Toast.LENGTH_LONG).show();return;}prefs.edit().putString("base",url).putString("token",token).apply();showBoard();});
        root.addView(label("也可以安装后，在电脑的新版页面点「连接个人版 App」，自动填入连接信息。",13));
    }
    private void showBoard() {
        base=prefs.getString("base","");String token=prefs.getString("token","");
        if(!validBase(base)||token.isEmpty()){settings();return;}
        LinearLayout root=layout();LinearLayout bar=new LinearLayout(this);bar.setPadding(dp(12),0,dp(12),0);bar.setGravity(Gravity.CENTER_VERTICAL);bar.setMinimumHeight(dp(56));TextView title=label("群务台·个人版",14);title.setSingleLine(true);title.setEllipsize(TextUtils.TruncateAt.END);bar.addView(title,new LinearLayout.LayoutParams(0,-2,1));Button config=new Button(this);config.setText("连接设置");bar.addView(config);config.setOnClickListener(v->settings());Button refresh=new Button(this);refresh.setText("刷新");bar.addView(refresh);root.addView(bar);
        error=label("",13);error.setPadding(16,4,16,4);error.setVisibility(View.GONE);root.addView(error);
        web=new WebView(this);root.addView(web,new LinearLayout.LayoutParams(-1,0,1));
        web.getSettings().setJavaScriptEnabled(true);web.getSettings().setDomStorageEnabled(true);web.getSettings().setAllowFileAccess(false);web.getSettings().setAllowContentAccess(false);
        web.setWebChromeClient(new android.webkit.WebChromeClient());
        web.setWebViewClient(new WebViewClient(){
            @Override public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest request){return external(request.getUrl());}
            @Override public boolean shouldOverrideUrlLoading(WebView view,String url){return external(Uri.parse(url));}
            private boolean external(Uri url){Uri origin=Uri.parse(base);if(origin.getScheme().equals(url.getScheme())&&origin.getHost().equals(url.getHost())&&origin.getPort()==url.getPort())return false;try{startActivity(new Intent(Intent.ACTION_VIEW,url));}catch(Exception e){Toast.makeText(MainActivity.this,"无法打开此链接",Toast.LENGTH_SHORT).show();}return true;}
            @Override public void onReceivedError(WebView view,WebResourceRequest request,WebResourceError failure){if(request.isForMainFrame()){error.setText("无法连接电脑。请确认 Tailscale 已连接，然后点刷新。");error.setVisibility(View.VISIBLE);}}
        });
        String home=base+"/?token="+Uri.encode(token);
        refresh.setOnClickListener(v->{error.setVisibility(View.GONE);web.loadUrl(home);});web.loadUrl(home);
    }
    @Override public void onBackPressed(){if(web!=null&&web.canGoBack())web.goBack();else super.onBackPressed();}
    @Override protected void onDestroy(){if(web!=null)web.destroy();super.onDestroy();}
}
