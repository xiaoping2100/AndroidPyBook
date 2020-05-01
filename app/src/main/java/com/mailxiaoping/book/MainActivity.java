package com.mailxiaoping.book;

import android.Manifest;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.os.AsyncTask;
import android.os.Bundle;

import androidx.appcompat.app.AppCompatActivity;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;

import android.os.Environment;
import android.util.Log;
import android.view.View;
import android.widget.AdapterView;
import android.widget.ArrayAdapter;
import android.widget.EditText;
import android.widget.ListView;
import android.widget.TextView;
import android.widget.Toast;

import com.chaquo.python.PyObject;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;

public class MainActivity extends AppCompatActivity
        implements AdapterView.OnItemClickListener, AdapterView.OnItemLongClickListener {
    private PyObject story;
    private final int max_list_view_data_len = 100;
    private final String list_view_data[] = new String[max_list_view_data_len];
    private ArrayAdapter adapters[] = new ArrayAdapter[1];
    private int selected_book_index = -1;
    final String path = Environment.getExternalStorageDirectory().getAbsolutePath() + "/download/xiaoping/";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);
        if (!Python.isStarted()) {
            Python.start(new AndroidPlatform(this));
        }

        ListView listView1 = findViewById(R.id.listView1);
        InitArrayAdapterData();
        ArrayAdapter arrayAdapter = new ArrayAdapter<String>(this,
                android.R.layout.simple_list_item_1, list_view_data);
        adapters[0] = arrayAdapter;
        listView1.setAdapter(arrayAdapter);
        listView1.setOnItemClickListener(this);


        checkStoragePermission();

        Python py = Python.getInstance();
        story = py.getModule("android").callAttr("main");
    }


    public View getItemViewOfListViewByPosition(ListView listView, int pos) {
        //参考https://blog.csdn.net/c15522627353/article/details/47186981
        //参考https://blog.csdn.net/weixin_34268169/article/details/85819660
        int firstListItemPosition = listView.getFirstVisiblePosition();
        int lastListItemPosition = firstListItemPosition
                + listView.getChildCount() - 1;

        if (pos < firstListItemPosition || pos > lastListItemPosition) {
            return listView.getAdapter().getView(pos, null, listView);
        } else {
            final int childIndex = pos - firstListItemPosition;
            return listView.getChildAt(childIndex);
        }
    }

    public void setListViewBackGround(ListView listView, int position) {
        for (int i = 0; i < list_view_data.length; i++) {
            if (list_view_data[i].equals(""))
                return;
            View v = getItemViewOfListViewByPosition(listView, i);
            if (position == i) {
                v.setBackgroundColor(Color.GREEN);
            } else {
                v.setBackgroundColor(Color.TRANSPARENT);
            }
        }
    }

    @Override
    public void onItemClick(AdapterView<?> parent, View view, int position, long id) {
//                Toast.makeText(MainActivity.this, "hello", Toast.LENGTH_SHORT).show();
        setListViewBackGround((ListView) parent, position);
        if (list_view_data[position].equals(""))
            selected_book_index = -1;
        else
            selected_book_index = position;
    }

    @Override
    public boolean onItemLongClick(AdapterView<?> parent, View view, int position, long id) {
        return false; //返回True表示不需要传递给onItemClick处理，返回False则需onItemClick继续处理处理
    }

    // 检查存储权限
    void checkStoragePermission() {
        if (ContextCompat.checkSelfPermission(MainActivity.this,
                Manifest.permission.WRITE_EXTERNAL_STORAGE) != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(MainActivity.this,
                    new String[]{Manifest.permission.WRITE_EXTERNAL_STORAGE},
                    1);
        }
    }

    public void InitArrayAdapterData() {
        selected_book_index = -1;
        for (int i = 0; i < max_list_view_data_len; i++)
            list_view_data[i] = "";
    }

    public void onClickBtn1(View view) {
        //下载书籍
        EditText editText1 = (EditText) findViewById(R.id.editText1);
        String info = editText1.getText().toString().trim();
        if (info.equals("")) {
            Toast.makeText(MainActivity.this, "请输入待查找书籍的书名或作者名", Toast.LENGTH_SHORT).show();
            return;
        }
        new DownloadInfoTask().execute(info);
    }


    private class DownloadInfoTask extends AsyncTask<String, String, Boolean> {
        String FINISH_FLAG_STRING;

        @Override
        protected Boolean doInBackground(String... params) {
            String info = params[0];
            String pre_statue, statue;
            FINISH_FLAG_STRING = story.get("FINISH_FLAG_STRING").toString();
            publishProgress("开始查询小说");
            story.callAttr("asyn_do_action_fetch_books", info);
            pre_statue = "";
            for (int i = 300; i >= 0; i--) {
                try {
                    Thread.sleep(100);
                } catch (InterruptedException e) {
                    e.printStackTrace();
                }
                statue = story.callAttr("asyn_get_statue_fetch_books").toString();
                if (statue.equals(FINISH_FLAG_STRING)) {
                    publishProgress(statue);
                    return true;
                }
                if (!statue.equals(pre_statue)) {
                    publishProgress(statue);
                    pre_statue = statue;
                }
            }
            publishProgress("查询超时");
            return false;
        }

        @Override
        protected void onProgressUpdate(String... values) {
            // 更新进度
            String statue = values[0];
            TextView tv1 = findViewById(R.id.textView1);
            if (statue.equals(FINISH_FLAG_STRING)) {  //查询成功
                // 刷新listview1列表并更新
                InitArrayAdapterData();
                java.util.List list = story.get("books").asList();
                for (int i = 0; i < list.size(); i++) {
                    if (i >= max_list_view_data_len)
                        break;
                    PyObject book = ((PyObject) list.get(i));
                    list_view_data[i] = String.format("%s 作者:%s %s",
                            book.get("name").toString(),
                            book.get("author").toString(),
                            book.get("brief").toString());
                }
                adapters[0].notifyDataSetChanged();
                tv1.setText("查询完成");
            } else {
                tv1.setText(statue);
            }
        }
    }

    public void onClickBtn2(View view) {
        //查询书籍信息
        if (selected_book_index == -1) {
            Toast.makeText(MainActivity.this, "请选择一本书", Toast.LENGTH_SHORT).show();
            return;
        }
        new DownloadBookTask().execute(selected_book_index);
    }

    private class DownloadBookTask extends AsyncTask<Integer, String, Boolean> {
        String FINISH_FLAG_STRING;

        @Override
        protected Boolean doInBackground(Integer... params) {
            int book_index = params[0];
            FINISH_FLAG_STRING = story.get("FINISH_FLAG_STRING").toString();
            String statue;
            publishProgress("开始获取章节信息");
            try {
                Thread.sleep(10);
            } catch (InterruptedException e) {
                e.printStackTrace();
            }
            story.callAttr("choice_book", book_index);
            publishProgress("获取章节信息完成");
            try {
                Thread.sleep(10);
            } catch (InterruptedException e) {
                e.printStackTrace();
            }
            story.callAttr("asyn_do_action_save_books", path);
            for (int i = 6000; i >= 0; i--) {
                try {
                    Thread.sleep(100);
                } catch (InterruptedException e) {
                    e.printStackTrace();
                }
                statue = story.callAttr("asyn_get_statue_save_books").toString();
                Log.v("main", statue);
                if (!statue.equals(FINISH_FLAG_STRING)) {
                    publishProgress(statue);
                } else {
                    statue = String.format("下载完成，文件名为%s", story.get("save_filename").toString());
                    publishProgress(statue);
                    return true;
                }
            }
            publishProgress("下载超时");
            return false;
        }

        @Override
        protected void onProgressUpdate(String... values) {
            // 更新进度
            TextView tv2 = findViewById(R.id.textView2);
            tv2.setText(values[0]);
        }
    }
}